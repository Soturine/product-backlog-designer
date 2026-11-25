"""prepare → preview → approve → apply → verify against a target, with a mock transport only.

- ``prepare`` compares the local package with a local snapshot of the target and emits a
  publication plan (schema ``publication-plan``): CREATE / UPDATE / UNCHANGED / CONFLICT / DEFERRED.
  Identity is the PBD ID recorded as a ``pbd-id:<ID>`` tag; titles never match items. No DELETE
  exists. Forbidden fields (assignee, state, iteration, area, completed/remaining work) are never
  written. A changed remote parent is a CONFLICT (re-parenting needs a person).
- ``approve`` binds the exact plan digest, target namespace, approver and time.
- ``apply`` runs only through ``authorize_apply`` and only on a mock transport. A write-ahead journal
  makes it resumable and idempotent: applied operations are not repeated, an ambiguous create is
  reconciled by identity before any retry, 429/5xx/timeouts are retried a bounded number of times,
  401/403 stop the run, a revision conflict (412) fails the operation without overwriting, a
  failed parent link leaves the item PARTIAL. Nothing is ever deleted.
- ``verify`` reads every touched item back in batches of at most 200 and compares the written
  fields and parent. A mock receipt can at most be MOCK_VERIFIED; it never proves a live target.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from pbd import SCHEMA_VERSION
from pbd.core.canonical import digest
from pbd.core.identity import derive
from pbd.integrations.authority import (
    AuthorizationDenied,
    RemoteAuthority,
    authorize_apply,
    plan_content_digest,
)
from pbd.integrations.azure.snapshot import HIERARCHY_REVERSE, MAX_BATCH, batches
from pbd.integrations.azure.transport import Transport, TransportError

FORBIDDEN_REFS = {
    "System.AssignedTo",
    "System.State",
    "System.Reason",
    "System.IterationPath",
    "System.AreaPath",
    "Microsoft.VSTS.Scheduling.RemainingWork",
    "Microsoft.VSTS.Scheduling.CompletedWork",
    "Microsoft.VSTS.Scheduling.TargetDate",
    "Microsoft.VSTS.Scheduling.StartDate",
    "Microsoft.VSTS.Scheduling.FinishDate",
}
RETRYABLE = {429, 500, 502, 503, 504, "timeout"}
STOPPING = {401, 403}
TAGS = "System.Tags"
HTML_FIELDS = {
    "System.Description",
    "Microsoft.VSTS.Common.AcceptanceCriteria",
    "Microsoft.VSTS.TCM.ReproSteps",
}


def _field_patch(fields: dict[str, Any]) -> list[dict[str, Any]]:
    """JSON Patch adds for fields, declaring HTML for rich multi-line fields (never Markdown)."""
    ops = [{"op": "add", "path": f"/fields/{k}", "value": v} for k, v in fields.items()]
    ops += [
        {"op": "add", "path": f"/multilineFieldsFormat/{k}", "value": "html"}
        for k in fields
        if k in HTML_FIELDS
    ]
    return ops


class PublishError(ValueError):
    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or [message]
        super().__init__(message + "".join(f"\n  - {e}" for e in self.errors[1:] if errors))


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        text = html.unescape(re.sub(r">\s+<", "><", value.strip()))
        return re.sub(r"\s+", " ", text)
    return value


def _tags(existing: Any, pbd_id: str, extra: Any = None) -> str:
    parts = [t.strip() for t in str(existing or "").split(";") if t.strip()]
    parts += [t.strip() for t in str(extra or "").split(";") if t.strip()]
    parts = [t for t in parts if not t.startswith("pbd-id:")] + [f"pbd-id:{pbd_id}"]
    return "; ".join(dict.fromkeys(parts))


# ------------------------------------------------------------------------------------- prepare
def managed_digest(fields: dict[str, Any], keys: list[str]) -> str:
    """Digest of the fields PBD manages for an item (normalized), to detect later human edits."""
    return digest({k: _norm(fields.get(k)) for k in sorted(keys) if k != TAGS})


def prepare(
    backlog: dict[str, Any],
    package: dict[str, Any],
    snapshot: dict[str, Any],
    target_namespace: str,
    published: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``published`` is the state recorded by the last verified publication (``published_state``)."""
    if snapshot["target"]["namespace"] != target_namespace:
        raise PublishError(
            f"snapshot target {snapshot['target']['namespace']} differs from the requested {target_namespace}"
        )
    if package.get("backlog_digest") != digest(backlog):
        raise PublishError("package was not built from this backlog (digest mismatch): rebuild the package")
    by_pbd: dict[str, list[dict[str, Any]]] = {}
    for wi in snapshot["items"]:
        for pid in wi["pbd_ids"]:
            by_pbd.setdefault(pid, []).append(wi)
    remote_by_id = {wi["id"]: wi for wi in snapshot["items"]}
    anchor = {"backlog": digest(backlog), "snapshot": snapshot["content_digest"], "target": target_namespace}
    ops: list[dict[str, Any]] = []
    state: dict[str, str] = {}
    for wi in package["work_items"]:
        pid = wi["pbd_id"]
        desired = {k: v for k, v in wi["fields"].items()}
        bad = sorted(set(desired) & FORBIDDEN_REFS)
        op: dict[str, Any] = {"op_id": derive("operation", {**anchor, "pbd": pid}), "pbd_id": pid}
        parent = wi.get("parent_pbd_id")
        matches = by_pbd.get(pid, [])
        if bad:
            op.update(action="CONFLICT", reason=f"package would write forbidden fields {bad}")
        elif len(matches) > 1:
            op.update(
                action="CONFLICT",
                reason=f"ambiguous identity: {len(matches)} remote items carry pbd-id:{pid}",
            )
        elif parent and state.get(parent) in ("CONFLICT", "DEFERRED"):
            op.update(action="DEFERRED", reason=f"parent {parent} is {state[parent]}")
        elif not matches:
            fields = {
                **desired,
                TAGS: _tags(None, pid, desired.get(TAGS)),
                "System.WorkItemType": wi["work_item_type"],
            }
            op.update(
                action="CREATE",
                fields=fields,
                links=[{"rel": HIERARCHY_REVERSE, "parent_pbd_id": parent}] if parent else [],
            )
        else:
            remote = matches[0]
            ref = {
                "system": "azure-devops",
                "namespace": target_namespace,
                "native_id": str(remote["id"]),
                "revision": remote["rev"],
            }
            if remote["fields"] is None:
                op.update(
                    action="DEFERRED",
                    external_ref=ref,
                    reason="remote fields unavailable in the snapshot (incomplete export)",
                )
            elif remote["type"] != wi["work_item_type"]:
                op.update(
                    action="CONFLICT",
                    external_ref=ref,
                    reason=f"remote type {remote['type']} differs from {wi['work_item_type']}",
                )
            else:
                desired[TAGS] = _tags(remote["fields"].get(TAGS), pid, desired.get(TAGS))
                changed = {k: v for k, v in desired.items() if _norm(remote["fields"].get(k)) != _norm(v)}
                last = (published or {}).get("items", {}).get(pid)
                if (
                    changed
                    and last
                    and remote["rev"] != last["rev"]
                    and managed_digest(remote["fields"], last["keys"]) != last["fields_digest"]
                ):
                    op.update(
                        action="CONFLICT",
                        external_ref=ref,
                        reason=(
                            f"edited in the target after the last publication (rev {last['rev']} -> "
                            f"{remote['rev']}); reconcile the human change before overwriting"
                        ),
                    )
                    ops.append(op)
                    state[pid] = op["action"]
                    continue
                links = []
                want_parent = by_pbd.get(parent, [{}])[0].get("id") if parent else None
                if parent and remote["parent"] is None:
                    links = [{"rel": HIERARCHY_REVERSE, "parent_pbd_id": parent}]
                elif parent and want_parent is not None and remote["parent"] != want_parent:
                    op.update(
                        action="CONFLICT",
                        external_ref=ref,
                        reason=f"remote parent {remote['parent']} differs; re-parenting needs a person",
                    )
                    ops.append(op)
                    state[pid] = op["action"]
                    continue
                elif remote["parent"] is not None and remote["parent"] not in remote_by_id and not parent:
                    links = []
                if changed or links:
                    op.update(
                        action="UPDATE",
                        external_ref=ref,
                        expected_revision=remote["rev"],
                        fields=changed,
                        links=links,
                    )
                else:
                    op.update(action="UNCHANGED", external_ref=ref)
        if op["action"] in ("CREATE", "UPDATE"):
            op["emitted_digest"] = digest({"fields": op.get("fields", {}), "links": op.get("links", [])})
        ops.append(op)
        state[pid] = op["action"]
    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "pbd.publication-plan",
        "plan_id": derive("plan", anchor),
        "run_id": backlog["run_id"],
        "backlog_digest": digest(backlog),
        "snapshot_digest": snapshot["digest"],
        "target": {"system": "azure-devops", "namespace": target_namespace, "profile": package["profile"]},
        "operations": ops,
        "approval": {"state": "unapproved"},
    }
    plan["plan_digest"] = plan_content_digest(plan)
    return plan


def preview(plan: dict[str, Any]) -> dict[str, Any]:
    from collections import Counter

    counts = Counter(o["action"] for o in plan["operations"])
    return {
        "kind": "pbd.publication-preview",
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "target": plan["target"],
        "counts": dict(sorted(counts.items())),
        "operations": [
            {
                "op_id": o["op_id"],
                "action": o["action"],
                "pbd_id": o["pbd_id"],
                "remote_id": (o.get("external_ref") or {}).get("native_id"),
                "fields": sorted((o.get("fields") or {}).keys()),
                "values": o.get("fields") or {},
                "links": o.get("links") or [],
                "reason": o.get("reason"),
            }
            for o in plan["operations"]
        ],
        "note": "Preview only. Nothing is written until this exact plan is approved for this exact target.",
        "deletes": 0,
    }


def approve(
    plan: dict[str, Any], target_namespace: str, approved_by: str, approved_at: str
) -> dict[str, Any]:
    if plan_content_digest(plan) != plan.get("plan_digest"):
        raise PublishError("plan content changed after its digest was computed; prepare again")
    if plan["target"]["namespace"] != target_namespace:
        raise PublishError("approval target differs from the plan target")
    if not approved_by.strip():
        raise PublishError("approved_by is required")
    out: dict[str, Any] = json.loads(json.dumps(plan))
    out["approval"] = {
        "state": "approved",
        "approved_plan_digest": plan["plan_digest"],
        "approved_target_namespace": target_namespace,
        "approved_by": approved_by,
        "approved_at": approved_at,
    }
    return out


# ------------------------------------------------------------------------------------- apply
class Journal:
    """Append-only write-ahead journal (JSON lines): intent before each call, result after."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.entries: list[dict[str, Any]] = []
        if self.path.exists():
            self.entries = [
                json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line
            ]

    def write(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    def done(self, plan_digest: str) -> dict[str, dict[str, Any]]:
        out = {}
        for e in self.entries:
            if (
                e.get("plan_digest") == plan_digest
                and e.get("phase") == "result"
                and e["outcome"] in ("APPLIED", "UNCHANGED", "PARTIAL")
            ):
                out[e["op_id"]] = e
        return out


def _call(
    fn: Callable[[], dict[str, Any]],
    retries: int,
    sleep: Callable[[float], None],
    reconcile: Callable[[], dict[str, Any] | None] | None = None,
) -> tuple[dict[str, Any] | None, str, str]:
    """Run a write with bounded retries. Returns (work item or None, outcome, detail)."""
    detail = ""
    for attempt in range(retries + 1):
        try:
            return fn(), "APPLIED", ""
        except TransportError as exc:
            detail = str(exc)
            if exc.status in STOPPING:
                return None, "STOP", detail
            if exc.status in ("timeout", 500, 502, 503, 504) and reconcile is not None:
                found = reconcile()
                if found is not None:
                    return found, "APPLIED", f"reconciled after: {detail}"
            if exc.status not in RETRYABLE or attempt == retries:
                return None, "FAILED", detail
            sleep(exc.retry_after if exc.retry_after is not None else min(2.0**attempt, 30.0))
    return None, "FAILED", detail  # pragma: no cover


def apply(
    plan: dict[str, Any],
    transport: Transport,
    authority: RemoteAuthority,
    journal_path: Path,
    *,
    retries: int = 3,
    sleep: Callable[[float], None] = lambda s: None,
) -> dict[str, Any]:
    if getattr(transport, "kind", None) != "mock":
        raise AuthorizationDenied("only the mock transport exists in this build; no live writes")
    authorize_apply(plan, authority, plan["target"]["namespace"])
    namespace = plan["target"]["namespace"]
    journal = Journal(journal_path)
    previous = journal.done(plan["plan_digest"])
    remote: dict[str, int] = {}
    for o in plan["operations"]:
        if o.get("external_ref"):
            remote[o["pbd_id"]] = int(o["external_ref"]["native_id"])
    for e in previous.values():
        if e.get("remote_id"):
            remote[e["pbd_id"]] = e["remote_id"]
    results: list[dict[str, Any]] = []
    stopped = ""

    def record(o: dict[str, Any], outcome: str, detail: str = "", wid: int | None = None) -> None:
        res: dict[str, Any] = {"op_id": o["op_id"], "outcome": outcome}
        if wid is not None:
            res["external_ref"] = {"system": "azure-devops", "namespace": namespace, "native_id": str(wid)}
        if detail:
            res["detail"] = detail
        results.append(res)
        journal.write(
            {
                "plan_digest": plan["plan_digest"],
                "phase": "result",
                "op_id": o["op_id"],
                "pbd_id": o["pbd_id"],
                "outcome": outcome,
                "remote_id": wid,
                "detail": detail,
            }
        )

    for o in plan["operations"]:
        if o["op_id"] in previous:
            prev = previous[o["op_id"]]
            results.append(
                {
                    "op_id": o["op_id"],
                    "outcome": prev["outcome"],
                    **(
                        {
                            "external_ref": {
                                "system": "azure-devops",
                                "namespace": namespace,
                                "native_id": str(prev["remote_id"]),
                            }
                        }
                        if prev.get("remote_id")
                        else {}
                    ),
                    "detail": "already applied (journal)",
                }
            )
            continue
        if stopped:
            record(o, "SKIPPED", f"not attempted: {stopped}")
            continue
        if o["action"] == "UNCHANGED":
            record(o, "UNCHANGED", "", remote.get(o["pbd_id"]))
            continue
        if o["action"] in ("CONFLICT", "DEFERRED"):
            record(o, "SKIPPED", f"{o['action']}: {o.get('reason', '')}")
            continue
        parent_links = [lk for lk in o.get("links", []) if lk.get("parent_pbd_id")]
        parent_id = remote.get(parent_links[0]["parent_pbd_id"]) if parent_links else None
        if parent_links and parent_id is None:
            record(o, "SKIPPED", f"parent {parent_links[0]['parent_pbd_id']} was not created or matched")
            continue
        journal.write(
            {
                "plan_digest": plan["plan_digest"],
                "phase": "intent",
                "op_id": o["op_id"],
                "pbd_id": o["pbd_id"],
            }
        )
        if o["action"] == "CREATE":
            fields = dict(o["fields"])
            wit = fields.pop("System.WorkItemType")
            patch = _field_patch(fields)

            def reconcile(pid: str = o["pbd_id"]) -> dict[str, Any] | None:
                found = transport.find_by_pbd_id(pid)
                return found[0] if len(found) == 1 else None

            wi: dict[str, Any] | None
            existing = transport.find_by_pbd_id(o["pbd_id"])
            if len(existing) > 1:
                record(o, "AMBIGUOUS", f"{len(existing)} remote items already carry pbd-id:{o['pbd_id']}")
                continue
            if existing:
                wi, outcome, detail = existing[0], "APPLIED", "already present (reconciled before create)"
            else:
                wi, outcome, detail = _call(partial(transport.create, wit, patch), retries, sleep, reconcile)
        else:
            wid = remote[o["pbd_id"]]
            patch = [{"op": "test", "path": "/rev", "value": o["expected_revision"]}]
            patch += _field_patch(o.get("fields") or {})
            wi, outcome, detail = (
                _call(partial(transport.update, wid, patch), retries, sleep)
                if len(patch) > 1
                else ({"id": wid, "rev": o["expected_revision"]}, "APPLIED", "")
            )
        if outcome == "STOP":
            stopped = f"authorization failure ({detail}); remaining operations were not attempted"
            record(o, "FAILED", detail)
            continue
        if wi is None:
            record(o, outcome, detail)
            continue
        remote[o["pbd_id"]] = int(wi["id"])
        if parent_id is not None:
            link = [
                {"op": "test", "path": "/rev", "value": wi["rev"]},
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {"rel": HIERARCHY_REVERSE, "url": transport.url_for(parent_id)},
                },
            ]

            def add_link(w: int = int(wi["id"]), body: list[dict[str, Any]] = link) -> dict[str, Any]:
                return transport.update(w, body)

            linked, _, ldetail = _call(add_link, retries, sleep)
            if linked is None:
                record(o, "PARTIAL", f"item written but parent link failed: {ldetail}", int(wi["id"]))
                continue
        record(o, "APPLIED", detail, int(wi["id"]))
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "kind": "pbd.publication-receipt",
        "receipt_id": derive("receipt", {"plan": plan["plan_digest"], "attempt": str(len(journal.entries))}),
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "transport": "mock",
        "results": results,
        "verification": {"status": "NOT_RUN"},
    }
    return receipt


# ------------------------------------------------------------------------------------- verify
def verify(plan: dict[str, Any], receipt: dict[str, Any], transport: Transport) -> dict[str, Any]:
    ops = {o["op_id"]: o for o in plan["operations"]}
    touched = {
        r["op_id"]: int(r["external_ref"]["native_id"])
        for r in receipt["results"]
        if r.get("external_ref") and r["outcome"] in ("APPLIED", "UNCHANGED", "PARTIAL")
    }
    ids = sorted(set(touched.values()))
    read: dict[int, dict[str, Any]] = {}
    deviations: list[str] = []
    for chunk in batches(ids, MAX_BATCH):
        for wi in transport.get(chunk):
            if not isinstance(wi.get("fields"), dict):
                deviations.append(f"{wi['id']}: read-back incomplete (fields missing)")
                continue
            read[wi["id"]] = wi
    pbd_to_remote = {ops[op]["pbd_id"]: wid for op, wid in touched.items()}
    for op_id, wid in touched.items():
        o = ops[op_id]
        got = read.get(wid)
        if got is None:
            deviations.append(f"{wid}: not found on read-back")
            continue
        for k, v in (o.get("fields") or {}).items():
            if k == "System.WorkItemType":
                if got["fields"].get(k) != v:
                    deviations.append(f"{wid}: type {wi['fields'].get(k)} != {v}")
                continue
            if _norm(got["fields"].get(k)) != _norm(v):
                deviations.append(f"{wid}: {k} differs after write")
        for link in o.get("links") or []:
            parent = pbd_to_remote.get(link.get("parent_pbd_id"))
            urls = [r.get("url", "") for r in got.get("relations") or [] if r.get("rel") == HIERARCHY_REVERSE]
            if parent is None or not any(u.endswith(f"/{parent}") for u in urls):
                deviations.append(f"{wid}: parent link to {link.get('parent_pbd_id')} missing")
    partial = [r["op_id"] for r in receipt["results"] if r["outcome"] in ("FAILED", "PARTIAL", "AMBIGUOUS")]
    out: dict[str, Any] = json.loads(json.dumps(receipt))
    out["verification"] = {
        "status": "MISMATCH" if deviations or partial else "MOCK_VERIFIED",
        "readback_digest": digest([read[i] for i in sorted(read)]),
        "deviations": deviations + [f"operation {p} did not complete" for p in partial],
    }
    return out


def published_state(
    plan: dict[str, Any], verified: dict[str, Any], package: dict[str, Any], transport: Transport
) -> dict[str, Any]:
    """What PBD last wrote and saw per item (revision + managed-field digest), for the next prepare."""
    ops = {o["op_id"]: o for o in plan["operations"]}
    keys = {w["pbd_id"]: sorted(w["fields"]) for w in package["work_items"]}
    touched = {
        ops[r["op_id"]]["pbd_id"]: int(r["external_ref"]["native_id"])
        for r in verified["results"]
        if r.get("external_ref") and r["outcome"] in ("APPLIED", "UNCHANGED")
    }
    items: dict[str, Any] = {}
    for chunk in batches(sorted(set(touched.values())), MAX_BATCH):
        for wi in transport.get(chunk):
            if not isinstance(wi.get("fields"), dict):
                continue
            pid = next(p for p, w in touched.items() if w == wi["id"])
            items[pid] = {
                "remote_id": wi["id"],
                "rev": wi["rev"],
                "keys": keys.get(pid, []),
                "fields_digest": managed_digest(wi["fields"], keys.get(pid, [])),
            }
    return {
        "kind": "pbd.azure-published-state",
        "target": plan["target"],
        "plan_digest": plan["plan_digest"],
        "verification": verified["verification"]["status"],
        "items": items,
    }


def compensation_candidates(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    """Items created by a run, listed for a PERSON to review. PBD never deletes or reverts them."""
    return [
        {
            "op_id": r["op_id"],
            "remote_id": r["external_ref"]["native_id"],
            "action": "review manually; no automatic delete",
        }
        for r in receipt["results"]
        if r["outcome"] in ("APPLIED", "PARTIAL") and r.get("external_ref")
    ]
