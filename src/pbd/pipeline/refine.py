"""Selective local refinement of a canonical backlog: propose → review diff → approve → apply.

An agent (or a person) writes a refinement proposal with targeted changes. ``plan`` validates every
change against the base backlog, renders before/after per change and a digest-bound plan. ``apply``
applies only the changes the owner approved, and only if the base backlog and the plan are
byte-for-byte the ones that were reviewed. Nothing is ever deleted: an obsolete criterion becomes
``superseded``/``out_of_scope`` with a rationale; items cannot be removed by refinement. Changed
items return to ``draft`` because the previous review and gates no longer describe them.
No tracker is touched.
"""

from __future__ import annotations

import copy
from typing import Any

from pbd.core.canonical import digest
from pbd.core.identity import derive
from pbd.render.sanitize import sanitize_html
from pbd.validation.invariants import check_backlog
from pbd.validation.schema import validate

OPS = {
    "update_title",
    "update_description",
    "set_field",
    "add_criterion",
    "update_criterion",
    "set_criterion_status",
    "add_item",
    "move_item",
}
FORBIDDEN_FIELDS = {
    "assigned_to",
    "completed_work",
    "remaining_work",
    "state",
    "iteration",
    "area",
    "target_date",
}
CRIT_STATUSES = {"confirmed", "proposed", "blocked", "out_of_scope", "superseded"}


class RefineError(ValueError):
    def __init__(self, message: str, errors: list[str]) -> None:
        super().__init__(message + "".join(f"\n  - {e}" for e in errors))
        self.errors = errors


def base_digest(backlog: dict[str, Any]) -> str:
    return digest({k: v for k, v in backlog.items() if k not in ("keys", "_digest")})


def _index(backlog: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], set[str]]:
    items = {i["id"]: i for i in backlog["items"]}
    crits = {c["id"]: c for c in backlog["criteria"]}
    claims = {c["id"] for c in backlog["claims"]}
    return items, crits, claims


def _apply_one(
    work: dict[str, Any], ch: dict[str, Any], label: str, anchor: str
) -> tuple[list[str], Any, Any, str]:
    """Apply a change in place on ``work``. Returns (errors, before, after, target_id)."""
    items, crits, claims = _index(work)
    op, target = ch.get("op"), ch.get("target")
    errs: list[str] = []
    if op not in OPS:
        return [f"{label}: op must be one of {sorted(OPS)} (deletion is not a refinement)"], None, None, ""
    if not str(ch.get("rationale", "")).strip():
        errs.append(f"{label}: rationale is required")
    refs = ch.get("claim_refs") or []
    bad_refs = [r for r in refs if r not in claims]
    if bad_refs:
        errs.append(f"{label}: unknown claim_refs {bad_refs}")
    if errs:
        return errs, None, None, ""
    if op in ("update_title", "update_description", "set_field", "move_item"):
        item = items.get(str(target))
        if item is None:
            return [f"{label}: target {target} is not an item"], None, None, ""
        if op == "update_title":
            value = str(ch.get("value", "")).strip()
            if not value:
                return [f"{label}: title cannot be empty"], None, None, ""
            before, item["title"] = item["title"], value
            return [], before, value, item["id"]
        if op == "update_description":
            before = (item.get("description") or {}).get("value", "")
            value = sanitize_html(str(ch.get("value", "")))
            item["description"] = {"format": "html", "value": value, "language": work["language"]}
            item.pop("content", None)  # the structured parts no longer match the edited text
            return [], before, value, item["id"]
        if op == "set_field":
            name = str(ch.get("field", ""))
            if name in FORBIDDEN_FIELDS:
                return (
                    [f"{label}: field {name} is never set by PBD (no invented assignment, dates or effort)"],
                    None,
                    None,
                    "",
                )
            state = ch.get("state", "proposed")
            if state == "confirmed" and not refs:
                return [f"{label}: a confirmed field needs claim_refs as evidence"], None, None, ""
            if state not in ("proposed", "confirmed", "unknown", "not_applicable"):
                return (
                    [f"{label}: state must be proposed, confirmed, unknown or not_applicable"],
                    None,
                    None,
                    "",
                )
            fv: dict[str, Any] = {
                "state": state,
                "rationale": str(ch["rationale"]),
                "review_status": "unreviewed",
            }
            if state in ("proposed", "confirmed"):
                if "value" not in ch:
                    return [f"{label}: value required for state {state}"], None, None, ""
                fv["value"] = ch["value"]
            if refs:
                claim_ev = {c["id"]: c for c in work["claims"]}
                fv["evidence"] = [ev for r in refs for ev in claim_ev[r]["evidence"]]
            before = (item.get("fields") or {}).get(name)
            item.setdefault("fields", {})[name] = fv
            return [], before, fv, item["id"]
        new_parent = ch.get("parent")
        if new_parent is not None and new_parent not in items:
            return [f"{label}: parent {new_parent} is not an item"], None, None, ""
        before, item["parent"] = item["parent"], new_parent
        return [], before, new_parent, item["id"]
    if op in ("update_criterion", "set_criterion_status"):
        crit = crits.get(str(target))
        if crit is None:
            return [f"{label}: target {target} is not a criterion"], None, None, ""
        before = copy.deepcopy(crit)
        if op == "set_criterion_status":
            status = ch.get("status")
            if status not in CRIT_STATUSES:
                return [f"{label}: status must be one of {sorted(CRIT_STATUSES)}"], None, None, ""
            if status == "confirmed" and not (crit["claim_refs"] or refs):
                return [f"{label}: a confirmed criterion needs claim_refs"], None, None, ""
            crit["status"] = status
            crit["rationale"] = str(ch["rationale"])
        else:
            outcomes = [str(o) for o in ch.get("expected_outcomes") or [] if str(o).strip()]
            if ch.get("text"):
                crit["text"] = str(ch["text"])
            if outcomes:
                crit["expected_outcomes"] = outcomes
            for opt in ("condition", "trigger"):
                if ch.get(opt):
                    crit[opt] = str(ch[opt])
        if refs:
            crit["claim_refs"] = sorted(set(crit["claim_refs"]) | set(refs))
        return [], before, copy.deepcopy(crit), crit["parent"]
    if op == "add_criterion":
        parent = items.get(str(target))
        if parent is None:
            return [f"{label}: target {target} is not an item"], None, None, ""
        outcomes = [str(o) for o in ch.get("expected_outcomes") or [] if str(o).strip()]
        if not outcomes:
            return [f"{label}: expected_outcomes required"], None, None, ""
        status = "confirmed" if refs and ch.get("status", "confirmed") == "confirmed" else "proposed"
        siblings = [c for c in work["criteria"] if c["parent"] == parent["id"]]
        new_crit: dict[str, Any] = {
            "id": derive("criterion", {"refinement": anchor, "change": label}),
            "parent": parent["id"],
            "order": len(siblings),
            "style": parent.get("acceptance_style", "list"),
            "expected_outcomes": outcomes,
            "claim_refs": sorted(refs),
            "origin": "human_edited",
            "status": status,
        }
        prefix = (siblings[0].get("visible_id", "AC-00").rsplit("-", 1)[0]) if siblings else "AC"
        new_crit["visible_id"] = f"{prefix}-{len(siblings) + 1:02d}"
        for opt in ("text", "condition", "trigger"):
            if ch.get(opt):
                new_crit[opt] = str(ch[opt])
        if status == "proposed":
            new_crit["rationale"] = str(ch["rationale"])
        work["criteria"].append(new_crit)
        return [], None, new_crit, parent["id"]
    # add_item
    itype = ch.get("type")
    if itype not in ("epic", "feature", "story", "enabler", "spike", "bug", "task"):
        return [f"{label}: type required"], None, None, ""
    parent_id = ch.get("parent")
    if parent_id is not None and parent_id not in items:
        return [f"{label}: parent {parent_id} is not an item"], None, None, ""
    title = str(ch.get("title", "")).strip()
    if not title:
        return [f"{label}: title required"], None, None, ""
    new_item: dict[str, Any] = {
        "id": derive(itype, {"refinement": anchor, "change": label}),
        "type": itype,
        "title": title,
        "parent": parent_id,
        "claim_refs": sorted(refs),
        "origin": "human_edited",
        "status": "draft",
    }
    if not refs:
        new_item["technical_rationale"] = str(ch["rationale"])
    if ch.get("description"):
        new_item["description"] = {
            "format": "html",
            "value": sanitize_html(str(ch["description"])),
            "language": work["language"],
        }
    work["items"].append(new_item)
    return [], None, new_item, new_item["id"]


def plan(backlog: dict[str, Any], proposal: Any) -> dict[str, Any]:
    """Validate a proposal against the base backlog and return a reviewable, digest-bound plan."""
    if (
        not isinstance(proposal, dict)
        or not isinstance(proposal.get("changes"), list)
        or not proposal["changes"]
    ):
        raise RefineError("refinement rejected", ["proposal needs a non-empty changes list"])
    author = proposal.get("author") or {}
    errors = [] if author.get("agent") else ["author.agent is required (who proposed the changes)"]
    anchor = base_digest(backlog)
    work = copy.deepcopy({k: v for k, v in backlog.items() if k not in ("keys", "_digest")})
    entries = []
    keys = [str(c.get("key", "")) for c in proposal["changes"]]
    if any(not k for k in keys) or len(set(keys)) != len(keys):
        errors.append("every change needs a unique key")
    for ch, key in zip(proposal["changes"], keys, strict=True):
        errs, before, after, target = _apply_one(work, ch, key, anchor)
        errors += errs
        if not errs:
            entries.append(
                {
                    "key": key,
                    "op": ch["op"],
                    "target": target,
                    "rationale": ch["rationale"],
                    "before": before,
                    "after": after,
                }
            )
    if not errors:
        issues = validate("backlog", work) or check_backlog(work)
        errors += [f"result: {i}" for i in issues]
    if errors:
        raise RefineError("refinement rejected (nothing planned)", errors)
    doc: dict[str, Any] = {
        "kind": "pbd.refinement-plan",
        "base_digest": anchor,
        "author": author,
        "changes": entries,
        "source_changes": proposal["changes"],
        "status": "proposed",
        "note": "Nothing is applied until the owner approves change keys with: pbd refine apply.",
    }
    doc["plan_digest"] = digest({k: v for k, v in doc.items() if k != "plan_digest"})
    return doc


def apply(
    backlog: dict[str, Any], plan_doc: dict[str, Any], approved: list[str], plan_digest: str
) -> dict[str, Any]:
    """Apply approved change keys. Refuses a changed base, a changed plan or unknown keys."""
    expected = digest({k: v for k, v in plan_doc.items() if k != "plan_digest"})
    errors = []
    if plan_doc.get("plan_digest") != expected or plan_digest != expected:
        errors.append("plan digest mismatch: the plan changed after review or a different plan was approved")
    if base_digest(backlog) != plan_doc.get("base_digest"):
        errors.append(
            "base backlog changed since the plan was made (conflict); plan again on the current backlog"
        )
    known = [c["key"] for c in plan_doc.get("changes", [])]
    chosen = known if approved == ["all"] else approved
    unknown = sorted(set(chosen) - set(known))
    if unknown:
        errors.append(f"unknown change keys {unknown}")
    if not chosen:
        errors.append("approve at least one change key (or 'all')")
    if errors:
        raise RefineError("refinement not applied", errors)
    anchor = plan_doc["base_digest"]
    work = copy.deepcopy({k: v for k, v in backlog.items() if k not in ("keys", "_digest")})
    source = {c["key"]: c for c in plan_doc.get("source_changes", [])}
    applied, touched = [], set()
    for entry in plan_doc["changes"]:
        if entry["key"] not in chosen:
            continue
        errs, _, _, target = _apply_one(work, source[entry["key"]], entry["key"], anchor)
        if errs:
            raise RefineError("refinement not applied (a change no longer fits)", errs)
        applied.append(entry["key"])
        touched.add(target)
    for item in work["items"]:
        if item["id"] in touched:
            item["status"] = "draft"
    issues = validate("backlog", work) or check_backlog(work)
    if issues:
        raise RefineError("refined backlog is invalid; nothing applied", [str(i) for i in issues])
    return {
        "backlog": work,
        "result": {
            "kind": "pbd.refinement-result",
            "base_digest": anchor,
            "plan_digest": expected,
            "applied": applied,
            "skipped": [k for k in known if k not in applied],
            "result_digest": base_digest(work),
            "invalidated": [
                "independent review",
                "gates",
                "plans and packages derived from the base backlog",
            ],
            "note": "Changed items are back to draft: run a new review/finalize before relying on gates.",
        },
    }


def diff_markdown(plan_doc: dict[str, Any], backlog: dict[str, Any]) -> str:
    titles = {i["id"]: i["title"] for i in backlog["items"]}
    lines = [
        "# Refinement plan (proposed — nothing applied)",
        "",
        f"Base: `{plan_doc['base_digest']}` · Plan: `{plan_doc['plan_digest']}`",
        "",
    ]
    for c in plan_doc["changes"]:
        target = titles.get(c["target"], c["target"])
        lines += [f"## {c['key']} · {c['op']} · {target}", "", f"Why: {c['rationale']}", ""]
        before = c["before"]
        after = c["after"]
        if isinstance(after, dict) and isinstance(before, dict):
            for k in sorted(set(before) | set(after)):
                if before.get(k) != after.get(k):
                    lines.append(f"- `{k}`: {before.get(k)!r} → {after.get(k)!r}")
        else:
            lines += [f"- before: {before!r}", f"- after: {after!r}"]
        lines.append("")
    lines.append(
        "Approve with: pbd refine apply --plan <plan.json> --approve <keys|all> --plan-digest <digest>"
    )
    return "\n".join(lines) + "\n"
