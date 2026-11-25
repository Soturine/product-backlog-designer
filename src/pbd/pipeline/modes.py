"""Local, deterministic modes that need no agent stage: check, clarify and profile inference.

- ``check``: structural health of a backlog file. Without normative sources nothing is said about
  requirement coverage; only structure (schema, hierarchy, traceability links, criteria presence,
  duplicate-title CANDIDATES) is reported. Optional empty fields, open parents and cross-cutting
  tasks are never defects by themselves.
- ``clarify``: the decisions a backlog is waiting for (open questions grouped by blocking/impact,
  findings that need a decision), as JSON and Markdown. A projection, not a new judgement.
- ``profile infer``: conventions observed in an existing backlog (native types, hierarchy pairs,
  fields in use, acceptance formats) and a DRAFT custom process profile for the owner to review.
  An observation is not a verified tracker configuration.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pbd import __version__
from pbd.core.canonical import bytes_digest, digest, loads_strict
from pbd.pipeline.importer import ImportError_, load_backlog
from pbd.profiles import CANONICAL_TYPES, FIELD_KEYS
from pbd.validation.invariants import check_backlog
from pbd.validation.schema import validate

CONTAINER_TYPES = {"epic", "feature"}
STORY_LIKE = {"story", "enabler", "spike", "bug"}


def _norm_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _load_any(
    path: Path, type_map: dict[str, str] | None
) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    """Return (format, canonical backlog or None, normalized import)."""
    data = Path(path).read_bytes()
    canonical = None
    if Path(path).suffix.lower() == ".json":
        doc = loads_strict(data)
        if isinstance(doc, dict) and doc.get("kind") == "pbd.backlog":
            canonical = doc
    imported = load_backlog(Path(path), type_map)
    return imported["format"], canonical, imported


# ---------------------------------------------------------------------------------------- check
def check(path: Path, type_map: dict[str, str] | None = None) -> dict[str, Any]:
    fmt, canonical, imp = _load_any(path, type_map)
    items = imp["items"]
    by_key = {i["key"]: i for i in items}
    crit_count = Counter(c["parent"] for c in imp["criteria"])
    errors: list[str] = []
    if canonical is not None:
        errors = [str(i) for i in validate("backlog", canonical)] or [
            str(i) for i in check_backlog(canonical)
        ]
    warnings: list[dict[str, Any]] = []
    for it in items:
        if it["type"] in STORY_LIKE and it["type"] != "bug" and not crit_count[it["key"]]:
            warnings.append({"code": "story_without_criteria", "item": it["native_id"]})
        parent = by_key.get(it["parent"]) if it["parent"] else None
        if parent and parent["type"] == "task":
            warnings.append({"code": "child_of_task", "item": it["native_id"], "parent": parent["native_id"]})
        if parent and it["type"] in CONTAINER_TYPES and parent["type"] not in CONTAINER_TYPES:
            warnings.append({"code": "container_under_work_item", "item": it["native_id"]})
    titles: dict[str, list[str]] = defaultdict(list)
    for it in items:
        titles[_norm_title(it["title"])].append(it["native_id"])
    candidates = [ids for t, ids in sorted(titles.items()) if t and len(ids) > 1]
    info = {
        "items_without_description": sum(1 for i in items if not i["description_raw"].strip()),
        "root_items": sum(1 for i in items if not i["parent"]),
        "unparented_note": "Items without a parent are reported, not judged: an open parent is not a defect.",
    }
    return {
        "kind": "pbd.check",
        "validator_version": __version__,
        "source_file": Path(path).name,
        "digest": imp["digest"],
        "format": fmt,
        "scope": "structural_only",
        "scope_note": "No normative sources were given: coverage, invention and scope are not assessed.",
        "items": {"total": len(items), "by_type": dict(sorted(Counter(i["type"] for i in items).items()))},
        "criteria": len(imp["criteria"]),
        "errors": errors,
        "warnings": warnings,
        "duplicate_title_candidates": candidates,
        "duplicate_note": "Equal titles are candidates for a person or reviewer, never confirmed duplicates.",
        "info": info,
        "import_notes": imp["notes"],
        "status": "fail" if errors else ("warn" if warnings else "pass"),
    }


# ---------------------------------------------------------------------------------------- clarify
IMPACT_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def clarify(backlog: dict[str, Any], keys: dict[str, str] | None = None) -> dict[str, Any]:
    keys = keys or backlog.get("keys") or {}
    titles = {i["id"]: i["title"] for i in backlog["items"]}
    crit_parent = {c["id"]: c["parent"] for c in backlog["criteria"]}

    def affected(ids: list[str]) -> list[dict[str, str]]:
        out = []
        for a in ids:
            item = crit_parent.get(a, a)
            if item in titles:
                out.append({"id": a, "key": keys.get(a, a), "item_title": titles[item]})
        return out

    questions = [q for q in backlog["questions"] if q["status"] == "open"]
    questions.sort(key=lambda q: (not q["blocking"], q["id"]))
    decisions = [
        f
        for f in backlog["findings"]
        if f.get("decision_needed") or f["classification"] in ("question", "ambiguous_source")
    ]
    decisions.sort(key=lambda f: (IMPACT_ORDER.get(f["severity"], 9), f["id"]))
    return {
        "kind": "pbd.clarifications",
        "backlog_digest": digest({k: v for k, v in backlog.items() if k != "keys"}),
        "language": backlog["language"],
        "summary": {
            "open_questions": len(questions),
            "blocking": sum(1 for q in questions if q["blocking"]),
            "decisions_from_findings": len(decisions),
        },
        "questions": [
            {
                "id": q["id"],
                "key": keys.get(q["id"], q["id"]),
                "text": q["text"],
                "impact": q["impact"],
                "blocking": q["blocking"],
                "options": q.get("options", []),
                "affects": affected(q["affects"]),
            }
            for q in questions
        ],
        "decisions": [
            {
                "finding": f["id"],
                "severity": f["severity"],
                "decision_needed": f.get("decision_needed") or f["recommendation"],
                "expected": f["expected"],
                "actual": f["actual"],
                "affects": affected(f["affects"]),
            }
            for f in decisions
        ],
        "note": "Answers become decisions only when recorded as a source (ADR/decision log) for a new run.",
    }


def clarify_markdown(doc: dict[str, Any]) -> str:
    s = doc["summary"]
    lines = [
        "# Clarifications",
        "",
        f"Open questions: {s['open_questions']} ({s['blocking']} blocking). "
        f"Decisions from findings: {s['decisions_from_findings']}.",
        "",
    ]
    for q in doc["questions"]:
        flag = "BLOCKING" if q["blocking"] else "non-blocking"
        lines.append(f"## {q['key']} [{flag}]")
        lines += [q["text"], "", f"Impact: {q['impact']}"]
        if q["options"]:
            lines.append("Options: " + " | ".join(q["options"]))
        if q["affects"]:
            lines.append("Affects: " + ", ".join(f"{a['key']} ({a['item_title']})" for a in q["affects"]))
        lines.append("")
    if doc["decisions"]:
        lines += ["## Decisions needed from findings", ""]
        for d in doc["decisions"]:
            lines.append(
                f"- [{d['severity']}] {d['decision_needed']} "
                f"(expected: {d['expected']}; actual: {d['actual']})"
            )
    lines += ["", doc["note"]]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------- profile
def infer_profile(
    path: Path, type_map: dict[str, str] | None = None, profile_id: str = "inferred"
) -> dict[str, Any]:
    """Observed conventions + a draft custom profile (unverified, for review)."""
    fmt, _, imp = _load_any(path, type_map)
    items = imp["items"]
    by_key = {i["key"]: i for i in items}
    native: dict[str, Counter[str]] = defaultdict(Counter)
    for it in items:
        native[it["type"]][it["native_type"]] += 1
    pairs = Counter(
        (by_key[i["parent"]]["native_type"], i["native_type"]) for i in items if i["parent"] in by_key
    )
    fields = Counter(f for i in items for f, v in i["fields_raw"].items() if v not in (None, ""))
    styles = Counter(i["acceptance_style"] for i in items if i["type"] in STORY_LIKE)
    types: dict[str, str | None] = {}
    ambiguous = {}
    for canon in CANONICAL_TYPES:
        seen = native.get(canon)
        if not seen:
            types[canon] = None
            continue
        top = seen.most_common()
        types[canon] = top[0][0]
        if len(top) > 1:
            ambiguous[canon] = [n for n, _ in top]
    field_map: dict[str, str | None] = dict.fromkeys(FIELD_KEYS)
    field_map.update({"title": "title", "description": "description"})
    for f in fields:
        if f in field_map:
            field_map[f] = f
    has_acceptance = bool(imp["criteria"])
    field_map["acceptance"] = "acceptance_criteria" if has_acceptance else None
    styled = [s for s in ("gherkin", "table", "list") if styles[s]]
    draft = {
        "id": re.sub(r"[^a-z0-9-]+", "-", profile_id.lower()).strip("-") or "inferred",
        "name": f"Inferred from {Path(path).name}",
        "tracker": "other",
        "types": types,
        "fields": field_map,
        "acceptance_types": sorted(t for t in STORY_LIKE if native.get(t)) if has_acceptance else [],
        "verified": False,
        "limitations": [
            "Inferred from one local backlog file; not verified against a tracker configuration.",
            "Review the type and field mapping before using it as --profile.",
        ],
    }
    from pbd.profiles import validate_profile

    problems = validate_profile(draft)
    return {
        "kind": "pbd.profile-inference",
        "source_file": Path(path).name,
        "digest": imp["digest"],
        "format": fmt,
        "observed": {
            "native_types": {k: dict(v) for k, v in sorted(native.items())},
            "hierarchy_pairs": [{"parent": p, "child": c, "count": n} for (p, c), n in sorted(pairs.items())],
            "fields_in_use": dict(sorted(fields.items())),
            "acceptance_styles": dict(sorted(styles.items())),
            "dominant_acceptance_style": styled[0] if len(styled) == 1 else ("mixed" if styled else "none"),
        },
        "ambiguous_types": ambiguous,
        "draft_profile": draft,
        "draft_problems": problems,
        "status": "proposed",
        "note": "Observations describe this file only; the draft profile needs owner review before use.",
    }


def load_json_backlog(path: Path) -> dict[str, Any]:
    data = Path(path).read_bytes()
    doc = loads_strict(data)
    if not isinstance(doc, dict) or doc.get("kind") != "pbd.backlog":
        raise ImportError_("expected a PBD canonical backlog (kind pbd.backlog)")
    doc.setdefault("_digest", bytes_digest(data))
    return doc
