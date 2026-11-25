"""Transports for the publication workflow. Only an in-memory fake exists in this build.

``FakeAzure`` models the parts of Azure Boards the workflow depends on: integer IDs, revisions
that increase on every write, JSON Patch with ``test /rev``, hierarchy relations, tag lookup for
identity reconciliation and the 200-item batch limit. Failures are injected per call to
reproduce 401/403/404/412/429/5xx, timeouts, incomplete responses, lost responses (applied but
not acknowledged) and parent-link failures. Nothing here opens a socket; there is no live
transport class at all, and ``authority.LIVE_TRANSPORT_AVAILABLE`` stays False.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pbd.integrations.azure.snapshot import HIERARCHY_REVERSE, MAX_BATCH, pbd_id_of

READ_ONLY = {
    "System.Id",
    "System.Rev",
    "System.CreatedDate",
    "System.ChangedDate",
    "System.CreatedBy",
    "System.ChangedBy",
}


class TransportError(RuntimeError):
    def __init__(self, status: int | str, message: str, retry_after: float | None = None) -> None:
        super().__init__(f"{status}: {message}")
        self.status = status
        self.retry_after = retry_after


class Transport(Protocol):
    kind: str

    def get(self, ids: list[int]) -> list[dict[str, Any]]: ...
    def create(self, wit: str, patch: list[dict[str, Any]]) -> dict[str, Any]: ...
    def update(self, wid: int, patch: list[dict[str, Any]]) -> dict[str, Any]: ...
    def find_by_pbd_id(self, pbd_id: str) -> list[dict[str, Any]]: ...
    def url_for(self, wid: int) -> str: ...


@dataclass
class Fault:
    """An injected failure: ``op`` in create/update/get/link, matched by call number or PBD id."""

    op: str
    status: int | str
    nth: int | None = None
    pbd_id: str | None = None
    times: int = 1
    retry_after: float | None = None
    applied: bool = False  # True: the write happens but the response is lost


@dataclass
class FakeAzure:
    """In-memory Azure Boards project (mock). State can be saved to a local JSON file."""

    namespace: str = "fabrikam-mock/backlog-mock"
    items: dict[int, dict[str, Any]] = field(default_factory=dict)
    faults: list[Fault] = field(default_factory=list)
    calls: list[tuple[str, Any]] = field(default_factory=list)
    next_id: int = 1000
    kind: str = "mock"

    # ------------------------------------------------------------------ persistence
    @classmethod
    def load(cls, path: Path) -> FakeAzure:
        if not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        fake = cls(namespace=data["namespace"], next_id=data["next_id"])
        fake.items = {int(k): v for k, v in data["items"].items()}
        return fake

    def save(self, path: Path) -> None:
        Path(path).write_text(
            json.dumps(
                {"namespace": self.namespace, "next_id": self.next_id, "items": self.items},
                ensure_ascii=False,
                indent=1,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ faults
    def _fault(self, op: str, pbd_id: str | None) -> Fault | None:
        count = sum(1 for c in self.calls if c[0] == op)
        for f in self.faults:
            if f.op != op or f.times <= 0:
                continue
            if f.nth is not None and f.nth != count:
                continue
            if f.pbd_id is not None and f.pbd_id != pbd_id:
                continue
            f.times -= 1
            return f
        return None

    def _raise(self, f: Fault) -> None:
        messages = {
            401: "unauthorized",
            403: "forbidden",
            404: "not found",
            412: "revision conflict",
            429: "too many requests",
            500: "server error",
            503: "service unavailable",
            "timeout": "timed out",
            "incomplete": "incomplete response",
        }
        raise TransportError(f.status, messages.get(f.status, "error"), f.retry_after)

    # ------------------------------------------------------------------ API
    def get(self, ids: list[int]) -> list[dict[str, Any]]:
        if len(ids) > MAX_BATCH:
            raise TransportError(400, f"batch of {len(ids)} exceeds {MAX_BATCH}")
        self.calls.append(("get", list(ids)))
        f = self._fault("get", None)
        if f and f.status == "incomplete":
            return [{"id": i} for i in ids if i in self.items]  # fields missing
        if f:
            self._raise(f)
        return [copy.deepcopy(self.items[i]) for i in ids if i in self.items]

    def url_for(self, wid: int) -> str:
        """Relation URL in the mock's own namespace (never a real tracker address)."""
        return f"mock://{self.namespace}/workItems/{wid}"

    def find_by_pbd_id(self, pbd_id: str) -> list[dict[str, Any]]:
        self.calls.append(("find", pbd_id))
        return [copy.deepcopy(w) for w in self.items.values() if pbd_id in pbd_id_of(w["fields"])]

    def _apply_patch(self, wi: dict[str, Any], patch: list[dict[str, Any]], pbd_id: str | None) -> None:
        for op in patch:
            path, value = op["path"], op.get("value")
            if op["op"] == "test":
                if path == "/rev" and value != wi["rev"]:
                    raise TransportError(412, f"expected revision {value}, current {wi['rev']}")
                continue
            if path.startswith("/fields/"):
                ref = path[len("/fields/") :]
                if ref in READ_ONLY:
                    raise TransportError(400, f"field {ref} is read-only")
                wi["fields"][ref] = value
            elif path == "/relations/-":
                f = self._fault("link", pbd_id)
                if f:
                    raise TransportError(f.status, "link failed: parent not found or not allowed")
                link: dict[str, Any] = value if isinstance(value, dict) else {}
                url = str(link.get("url", ""))
                target = url.rstrip("/").rsplit("/", 1)[-1]
                if not target.isdigit() or int(target) not in self.items:
                    raise TransportError(400, f"relation target {url} does not exist")
                rels = wi.setdefault("relations", [])
                if link not in rels:
                    if link.get("rel") == HIERARCHY_REVERSE and any(
                        r["rel"] == HIERARCHY_REVERSE for r in rels
                    ):
                        raise TransportError(400, "work item already has a parent")
                    rels.append(link)
            elif path.startswith("/multilineFieldsFormat/"):
                wi.setdefault("multilineFieldsFormat", {})[path.rsplit("/", 1)[-1]] = value

    def create(self, wit: str, patch: list[dict[str, Any]]) -> dict[str, Any]:
        pbd_id = next(
            (
                v
                for p in patch
                if p["path"] == "/fields/System.Tags"
                for v in pbd_id_of({"System.Tags": p["value"]})
            ),
            None,
        )
        self.calls.append(("create", pbd_id))
        f = self._fault("create", pbd_id)
        if f and not f.applied:
            self._raise(f)
        wi: dict[str, Any] = {
            "id": self.next_id,
            "rev": 1,
            "fields": {"System.WorkItemType": wit},
            "relations": [],
        }
        self._apply_patch(wi, patch, pbd_id)
        self.items[wi["id"]] = wi
        self.next_id += 1
        if f and f.applied:
            self._raise(f)  # applied, but the caller never sees the response
        return copy.deepcopy(wi)

    def update(self, wid: int, patch: list[dict[str, Any]]) -> dict[str, Any]:
        self.calls.append(("update", wid))
        f = self._fault("update", None)
        if f and not f.applied:
            self._raise(f)
        if wid not in self.items:
            raise TransportError(404, f"work item {wid} not found")
        wi = copy.deepcopy(self.items[wid])
        self._apply_patch(wi, patch, None)
        wi["rev"] += 1
        self.items[wid] = wi
        if f and f.applied:
            self._raise(f)
        return copy.deepcopy(wi)

    def snapshot_doc(self) -> dict[str, Any]:
        org, _, project = self.namespace.partition("/")
        return {
            "kind": "pbd.azure-snapshot",
            "target": {"organization": org, "project": project},
            "pages": [{"value": [copy.deepcopy(self.items[i]) for i in sorted(self.items)]}],
        }
