"""Referential and structural invariants of a canonical backlog (beyond JSON Schema).

These are deterministic checks only. Passing them proves structural integrity, never
semantic coverage or quality.
"""

from __future__ import annotations

from collections import Counter
from graphlib import CycleError, TopologicalSorter
from typing import Any

from pbd.validation.schema import Issue

# Default generic hierarchy (profile may narrow it). Value: allowed parent types; None = root allowed.
DEFAULT_ALLOWED_PARENTS: dict[str, set[str | None]] = {
    "epic": {None},
    "feature": {"epic", None},
    "story": {"feature", "epic", None},
    "enabler": {"feature", "epic", None},
    "spike": {"feature", "epic", "story", "enabler", None},
    "bug": {"feature", "story", None},
    "task": {"story", "enabler", "spike", "bug"},
}
ACCEPTANCE_PARENTS = {"story", "enabler", "bug", "feature", "spike"}
ORDERING_RELATIONS = {"predecessor"}


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("id")) for row in rows]


def check_backlog(
    doc: dict[str, Any], allowed_parents: dict[str, set[str | None]] | None = None
) -> list[Issue]:
    allowed = allowed_parents or DEFAULT_ALLOWED_PARENTS
    issues: list[Issue] = []
    collections = [
        "sources",
        "claims",
        "items",
        "criteria",
        "relations",
        "questions",
        "decisions",
        "findings",
    ]

    # 1. Global uniqueness of every identifier across all collections.
    all_ids = [i for name in collections for i in _ids(doc.get(name, []))]
    for ident, count in Counter(all_ids).items():
        if count > 1:
            issues.append(Issue("$", f"duplicate identifier {ident} ({count} occurrences)", "duplicate_id"))

    sources = {s["id"]: s for s in doc.get("sources", [])}
    claims = {c["id"]: c for c in doc.get("claims", [])}
    items = {i["id"]: i for i in doc.get("items", [])}
    criteria = {c["id"]: c for c in doc.get("criteria", [])}
    decisions = {d["id"]: d for d in doc.get("decisions", [])}
    known = set(all_ids)

    def check_locators(evidence: list[dict[str, Any]], where: str) -> None:
        for index, ev in enumerate(evidence or []):
            loc = ev.get("locator")
            if not loc:
                continue
            src = sources.get(loc.get("source_id"))
            if src is None:
                issues.append(
                    Issue(
                        f"{where}.evidence[{index}]", f"unknown source {loc.get('source_id')}", "dangling_ref"
                    )
                )
            elif src.get("version") != loc.get("source_version"):
                issues.append(
                    Issue(
                        f"{where}.evidence[{index}]",
                        f"locator cites {loc.get('source_version')!r}; source is {src.get('version')!r}",
                        "stale_locator",
                    )
                )

    # 2. Claims: locators resolve; supersession edges resolve and are symmetric.
    for cid, claim in claims.items():
        check_locators(claim.get("evidence", []), cid)
        temporal = claim.get("temporal", {})
        for other in temporal.get("superseded_by", []):
            if other not in claims and other not in decisions:
                issues.append(Issue(cid, f"superseded_by references unknown {other}", "dangling_ref"))
        for other in temporal.get("supersedes", []):
            if other not in claims:
                issues.append(Issue(cid, f"supersedes references unknown claim {other}", "dangling_ref"))
            elif cid not in claims[other].get("temporal", {}).get("superseded_by", []):
                issues.append(
                    Issue(
                        cid,
                        f"supersession with {other} is not recorded on both sides",
                        "asymmetric_supersession",
                    )
                )
        covered_by = claim.get("disposition", {}).get("covered_by", [])
        for ref in covered_by:
            if ref not in items and ref not in criteria:
                issues.append(
                    Issue(cid, f"covered_by references unknown item/criterion {ref}", "dangling_ref")
                )

    # 3. Items: parents exist, allowed parent type, claim refs resolve, no hierarchy cycles.
    graph: dict[str, set[str]] = {}
    for iid, item in items.items():
        parent = item.get("parent")
        itype = item.get("type")
        allowed_for = allowed.get(str(itype), set())
        if parent is None:
            if None not in allowed_for:
                issues.append(Issue(iid, f"{itype} requires a parent", "orphan"))
        elif parent not in items:
            issues.append(Issue(iid, f"parent {parent} does not exist", "dangling_ref"))
        else:
            ptype = items[parent].get("type")
            if ptype not in allowed_for:
                issues.append(Issue(iid, f"{itype} cannot be a child of {ptype}", "invalid_parent"))
            graph.setdefault(iid, set()).add(parent)
        for ref in item.get("claim_refs", []):
            if ref not in claims:
                issues.append(Issue(iid, f"claim ref {ref} does not exist", "dangling_ref"))
        for ext in item.get("external_refs", []):
            if str(ext.get("native_id", "")).startswith("PBD-"):
                issues.append(Issue(iid, "tracker namespace contains a PBD identifier", "namespace_mix"))
    try:
        TopologicalSorter(graph).prepare()
    except CycleError as exc:
        issues.append(Issue("$.items", f"hierarchy cycle: {exc.args[1]}", "cycle"))

    # Two external refs in the same tracker namespace must not point at different PBD items.
    seen_ext: dict[tuple[str, str, str], str] = {}
    for iid, item in items.items():
        for ext in item.get("external_refs", []):
            key = (ext.get("system"), ext.get("namespace"), ext.get("native_id"))
            if key in seen_ext and seen_ext[key] != iid:
                issues.append(
                    Issue(iid, f"tracker id {key[2]} already bound to {seen_ext[key]}", "duplicate_binding")
                )
            seen_ext[key] = iid

    # 4. Criteria: parent exists and may own acceptance; claims resolve.
    for acid, crit in criteria.items():
        parent = items.get(crit.get("parent"))
        if parent is None:
            issues.append(Issue(acid, f"parent {crit.get('parent')} does not exist", "dangling_ref"))
        elif parent.get("type") not in ACCEPTANCE_PARENTS:
            issues.append(
                Issue(acid, f"{parent.get('type')} cannot own acceptance criteria", "invalid_parent")
            )
        for ref in crit.get("claim_refs", []):
            if ref not in claims:
                issues.append(Issue(acid, f"claim ref {ref} does not exist", "dangling_ref"))
        check_locators(crit.get("evidence", []), acid)

    # 5. Relations: endpoints resolve; ordering relations acyclic; no self-loops.
    order: dict[str, set[str]] = {}
    for rel in doc.get("relations", []):
        rid, src, tgt = rel.get("id"), rel.get("source"), rel.get("target")
        if src not in known:
            issues.append(Issue(str(rid), f"relation source {src} does not exist", "dangling_ref"))
        if isinstance(tgt, str):
            if tgt not in known:
                issues.append(Issue(str(rid), f"relation target {tgt} does not exist", "dangling_ref"))
            if tgt == src:
                issues.append(Issue(str(rid), "relation points to itself", "self_loop"))
            if rel.get("type") in ORDERING_RELATIONS and rel.get("status") != "rejected":
                # predecessor: source must finish before target -> target depends on source
                order.setdefault(tgt, set()).add(str(src))
    try:
        TopologicalSorter(order).prepare()
    except CycleError as exc:
        issues.append(Issue("$.relations", f"dependency cycle: {exc.args[1]}", "cycle"))

    # 6. Questions/decisions/findings references.
    for q in doc.get("questions", []):
        for ref in q.get("affects", []):
            if ref not in known:
                issues.append(Issue(q["id"], f"affects unknown {ref}", "dangling_ref"))
        if q.get("answer_decision") and q["answer_decision"] not in decisions:
            issues.append(Issue(q["id"], "answer_decision does not exist", "dangling_ref"))
    for d in doc.get("decisions", []):
        for ref in d.get("supersedes_claims", []):
            if ref not in claims:
                issues.append(Issue(d["id"], f"supersedes unknown claim {ref}", "dangling_ref"))
    for f in doc.get("findings", []):
        for ref in f.get("affects", []):
            if ref not in known:
                issues.append(Issue(f["id"], f"affects unknown {ref}", "dangling_ref"))

    issues.extend(_reciprocity(claims, items, criteria, decisions, doc.get("relations", [])))
    return issues


_INACTIVE_CLAIM = {"SUPERSEDED", "OUT_OF_SCOPE"}
_INACTIVE_WORK = {"superseded", "out_of_scope"}


def _reciprocity(
    claims: dict[str, dict[str, Any]],
    items: dict[str, dict[str, Any]],
    criteria: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    relations: list[dict[str, Any]],
) -> list[Issue]:
    """Two-way consistency between claims, work, criteria, decisions and relations."""
    issues: list[Issue] = []
    work = {**items, **criteria}

    # Forward coverage must be backed by a reverse trace link.
    for cid, claim in claims.items():
        for ref in claim.get("disposition", {}).get("covered_by", []):
            target = work.get(ref)
            if target is not None and cid not in target.get("claim_refs", []):
                issues.append(
                    Issue(cid, f"covered_by {ref} but {ref} does not trace back", "trace_reciprocity")
                )

    # Active work must not rely on superseded or out-of-scope obligations.
    for wid, w in work.items():
        active = (
            w.get("status") not in _INACTIVE_WORK and (w.get("temporal") or {}).get("status") != "superseded"
        )
        for ref in w.get("claim_refs", []):
            traced = claims.get(ref)
            if traced is None or not active:
                continue
            if traced.get("disposition", {}).get("status") in _INACTIVE_CLAIM:
                issues.append(Issue(wid, f"active work traces to inactive claim {ref}", "stale_scope"))

    # A criterion's claims must be within its parent's traced scope.
    for acid, crit in criteria.items():
        parent = items.get(crit.get("parent", ""))
        if parent is None:
            continue
        outside = set(crit.get("claim_refs", [])) - set(parent.get("claim_refs", []))
        if outside:
            issues.append(
                Issue(acid, f"criterion traces claims absent from parent: {sorted(outside)}", "trace_scope")
            )

    # Supersession must be recorded on both the decision and the claim.
    for did, dec in decisions.items():
        for ref in dec.get("supersedes_claims", []):
            superseded = claims.get(ref)
            if superseded is None:
                continue
            temporal = superseded.get("temporal", {})
            if did not in temporal.get("superseded_by", []) or temporal.get("status") != "superseded":
                issues.append(
                    Issue(did, f"claim {ref} does not record supersession by {did}", "supersession")
                )
            if dec.get("status") != "approved":
                issues.append(Issue(did, "only approved decisions may supersede claims", "supersession"))
    for cid, claim in claims.items():
        for ref in claim.get("temporal", {}).get("superseded_by", []):
            decision = decisions.get(ref)
            if decision is not None and cid not in decision.get("supersedes_claims", []):
                issues.append(Issue(cid, f"decision {ref} does not list this claim", "supersession"))

    # Relations: no duplicate typed edges.
    seen: set[tuple[str, str, str]] = set()
    for rel in relations:
        target = rel.get("target")
        key = (str(rel.get("type")), str(rel.get("source")), str(target) if isinstance(target, str) else "")
        if isinstance(target, str) and key in seen:
            issues.append(Issue(str(rel.get("id")), "duplicate relation edge", "duplicate_relation"))
        seen.add(key)
    return issues
