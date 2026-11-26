"""Local Azure DevOps snapshots: import, normalize and derive a dynamic process profile.

A snapshot is a LOCAL file the owner exported and authorized (never fetched by PBD in this build).
Accepted shapes:

- ``{"kind": "pbd.azure-snapshot", "target": {"organization", "project"}, "metadata": {...},
  "pages": [{"value": [work items], "continuationToken": "..."}]}``
- a single REST-like page ``{"value": [...], "count": n}`` (target must then be given explicitly).

Work items keep the REST shape: ``id``, ``rev``, ``fields`` (reference names) and ``relations``.
Absent, unavailable and unknown stay distinct: a field missing from an item is ``absent``;
metadata the export did not include is ``unavailable``; it is never filled with defaults.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pbd.core.canonical import bytes_digest, digest, loads_strict

MAX_BATCH = 200
HIERARCHY_REVERSE = "System.LinkTypes.Hierarchy-Reverse"
PBD_TAG = re.compile(r"(?:^|;\s*)pbd-id:(PBD-[A-Z]+-[0-9A-HJKMNP-TV-Z]{12})(?=;|$)")
KNOWN_PROCESSES = {
    "agile": {"User Story", "Feature", "Epic", "Task", "Bug"},
    "scrum": {"Product Backlog Item", "Feature", "Epic", "Task", "Bug"},
    "basic": {"Issue", "Epic", "Task"},
    "cmmi": {"Requirement", "Feature", "Epic", "Task", "Bug"},
}
CANONICAL_BY_NATIVE = {
    "Epic": "epic",
    "Feature": "feature",
    "User Story": "story",
    "Product Backlog Item": "story",
    "Requirement": "story",
    "Issue": "story",
    "Bug": "bug",
    "Task": "task",
}


class SnapshotError(ValueError):
    pass


def batches(ids: list[int], size: int = MAX_BATCH) -> list[list[int]]:
    """Split IDs into detail batches of at most 200 (the work-items batch API limit)."""
    if size < 1 or size > MAX_BATCH:
        raise SnapshotError(f"batch size must be 1..{MAX_BATCH}")
    return [ids[i : i + size] for i in range(0, len(ids), size)]


def pbd_id_of(fields: dict[str, Any]) -> list[str]:
    """PBD identities recorded in tags (``pbd-id:<ID>``). More than one is an ambiguity."""
    return PBD_TAG.findall(str(fields.get("System.Tags") or ""))


def _parent_id(relations: list[dict[str, Any]] | None) -> int | None:
    parents = [r for r in relations or [] if r.get("rel") == HIERARCHY_REVERSE]
    if not parents:
        return None
    url = str(parents[0].get("url", ""))
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


def _check_normalized(doc: dict[str, Any]) -> None:
    tgt = doc.get("target") or {}
    org, project = tgt.get("organization"), tgt.get("project")
    if (
        not org
        or not project
        or tgt.get("namespace") != f"{org}/{project}"
        or tgt.get("system") != "azure-devops"
    ):
        raise SnapshotError("normalized snapshot target must name organization, project and their namespace")
    ids: set[int] = set()
    for n, item in enumerate(doc["items"]):
        wid = item.get("id") if isinstance(item, dict) else None
        if not isinstance(wid, int) or isinstance(wid, bool):
            raise SnapshotError(f"normalized snapshot item {n}: integer id required")
        if wid in ids:
            raise SnapshotError(f"normalized snapshot: work item {wid} appears twice")
        ids.add(wid)
        fields, rels = item.get("fields"), item.get("relations")
        if (fields is None) != (item.get("fields_state") == "unavailable") or not (
            fields is None or isinstance(fields, dict)
        ):
            raise SnapshotError(f"normalized snapshot item {wid}: fields and fields_state disagree")
        if (rels is None) != (item.get("relations_state") == "unavailable") or not (
            rels is None or isinstance(rels, list)
        ):
            raise SnapshotError(f"normalized snapshot item {wid}: relations and relations_state disagree")
        if fields is not None and item.get("type") != fields.get("System.WorkItemType"):
            raise SnapshotError(f"normalized snapshot item {wid}: type disagrees with its fields")


def load_snapshot(path: Path, target: dict[str, str] | None = None) -> dict[str, Any]:
    data = Path(path).read_bytes()
    doc = loads_strict(data)
    if not isinstance(doc, dict):
        raise SnapshotError("snapshot must be a JSON object")
    if doc.get("kind") == "pbd.azure-snapshot-normalized":
        # D9: the output of `pbd azure snapshot` is accepted by prepare. A digest proves integrity,
        # not authenticity (anyone can recompute it), so the content is re-validated before use.
        if not isinstance(doc.get("items"), list) or doc.get("content_digest") != digest(doc["items"]):
            raise SnapshotError(
                "normalized snapshot was altered after normalization (content digest mismatch)"
            )
        _check_normalized(doc)
        return dict(doc)
    if doc.get("kind") == "pbd.azure-snapshot":
        pages = doc.get("pages")
        tgt = doc.get("target") or target
        metadata = doc.get("metadata")
    elif isinstance(doc.get("value"), list):
        pages, tgt, metadata = [doc], target, None
    else:
        raise SnapshotError(
            "unsupported snapshot: expected kind pbd.azure-snapshot or a REST page with 'value'"
        )
    if not isinstance(pages, list) or not pages:
        raise SnapshotError("snapshot has no pages")
    if not tgt or not tgt.get("organization") or not tgt.get("project"):
        raise SnapshotError("snapshot target (organization and project) is required")
    notes: list[str] = []
    if pages[-1].get("continuationToken"):
        notes.append("last page has a continuationToken: the export is truncated; missing items are unknown")
    seen: dict[int, dict[str, Any]] = {}
    for n, page in enumerate(pages):
        for wi in page.get("value") or []:
            if not isinstance(wi, dict) or not isinstance(wi.get("id"), int):
                raise SnapshotError(f"page {n}: work item without integer id")
            if wi["id"] in seen:
                if wi.get("rev") != seen[wi["id"]].get("rev"):
                    raise SnapshotError(f"work item {wi['id']} appears twice with different revisions")
                continue
            if not isinstance(wi.get("fields"), dict):
                notes.append(f"work item {wi['id']}: fields unavailable (incomplete response)")
            seen[wi["id"]] = wi
    items = []
    for wid in sorted(seen):
        wi = seen[wid]
        fields = wi.get("fields") if isinstance(wi.get("fields"), dict) else None
        items.append(
            {
                "id": wid,
                "rev": wi.get("rev"),
                "type": (fields or {}).get("System.WorkItemType"),
                "fields": fields,
                "fields_state": "present" if fields is not None else "unavailable",
                "relations": wi.get("relations") if isinstance(wi.get("relations"), list) else None,
                "relations_state": "present" if isinstance(wi.get("relations"), list) else "unavailable",
                "parent": _parent_id(wi.get("relations")),
                "pbd_ids": pbd_id_of(fields or {}),
            }
        )
    namespace = f"{tgt['organization']}/{tgt['project']}"
    return {
        "kind": "pbd.azure-snapshot-normalized",
        "target": {
            "system": "azure-devops",
            "namespace": namespace,
            **{k: tgt[k] for k in ("organization", "project")},
        },
        "source_file": Path(path).name,
        "digest": bytes_digest(data),
        "items": items,
        "metadata": metadata if isinstance(metadata, dict) else None,
        "metadata_state": "present" if isinstance(metadata, dict) else "unavailable",
        "notes": notes,
        "content_digest": digest(items),
    }


def discover_profile(snapshot: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dynamic profile from snapshot metadata. Without metadata, only observed types are known."""
    meta = snapshot.get("metadata") or {}
    wits = meta.get("work_item_types") if isinstance(meta.get("work_item_types"), list) else None
    observed = sorted({i["type"] for i in snapshot["items"] if i["type"]})
    names = [w.get("name") for w in wits] if wits else observed
    process = meta.get("process")
    if not process:
        guesses = [p for p, types in KNOWN_PROCESSES.items() if set(names) >= types]
        process = guesses[0] if len(guesses) == 1 else "unknown"
    types: dict[str, str | None] = dict.fromkeys(
        ("epic", "feature", "story", "enabler", "spike", "bug", "task")
    )
    for name in names:
        canon = CANONICAL_BY_NATIVE.get(str(name))
        if canon and types.get(canon) is None:
            types[canon] = name
    if types["story"]:
        types["enabler"] = types["enabler"] or types["story"]
        types["spike"] = types["spike"] or types["story"]
    fields: dict[str, dict[str, Any]] = {}
    for w in wits or []:
        for f in w.get("fields") or []:
            ref = f.get("referenceName")
            if not ref:
                continue
            entry = fields.setdefault(
                ref, {"types": [], "required_in": [], "read_only": bool(f.get("readOnly"))}
            )
            entry["types"].append(w.get("name"))
            if f.get("alwaysRequired"):
                entry["required_in"].append(w.get("name"))
            if f.get("allowedValues"):
                entry["allowed_values"] = list(f["allowedValues"])
    return {
        "kind": "pbd.azure-discovered-profile",
        "target": snapshot["target"],
        "process": process,
        "types": types,
        "work_item_types": names,
        "types_state": "present" if wits else "observed_only",
        "fields": fields,
        "fields_state": "present" if wits else "unavailable",
        "link_types": meta.get("link_types") if isinstance(meta.get("link_types"), list) else None,
        "verified": False,
        "note": "Discovered from a local snapshot export; not a live inspection of the project.",
        "base_profile": (base or {}).get("id"),
    }
