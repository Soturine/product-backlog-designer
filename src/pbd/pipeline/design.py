"""Claims reconciliation and backlog design submissions, compiled into the canonical backlog.

Semantic decisions (what a claim is, how to slice stories, which criteria apply) come from the
agent. The runtime only checks completeness, references, shapes and invariants, assigns stable
IDs and renders native rich text. All submissions are all-or-nothing.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pbd import SCHEMA_VERSION, vocab
from pbd.core.canonical import digest
from pbd.core.identity import derive
from pbd.pipeline.reading import normalize_for_match
from pbd.pipeline.run import Run, RunError, require_stage
from pbd.render.richtext import CONTENT_KINDS, RichTextError, description_html, validate_content
from pbd.validation.invariants import check_backlog
from pbd.validation.schema import validate

TYPE_LEVEL = {
    "epic": "epics",
    "feature": "features",
    "story": "stories",
    "enabler": "stories",
    "spike": "stories",
    "bug": "stories",
    "task": "tasks",
}
TYPE_CONTENT = {
    "epic": {"epic"},
    "feature": {"feature"},
    "story": {"role_goal_benefit", "job_story"},
    "enabler": {"enabler"},
    "spike": {"spike"},
    "task": {"task"},
    "bug": {"bug"},
}
STORY_FORMAT = {
    "role_goal_benefit": "role_goal_benefit",
    "job_story": "job_story",
    "enabler": "enabler",
    "spike": "spike",
}
ALLOWED_FIELDS = {
    "priority",
    "story_points",
    "original_estimate",
    "activity",
    "tags",
    "risk",
    "business_value",
    "time_criticality",
    "value_area",
}
FORBIDDEN_FIELDS = {
    "assigned_to",
    "completed_work",
    "remaining_work",
    "state",
    "iteration",
    "iteration_path",
    "area_path",
    "start_date",
    "target_date",
    "finish_date",
    "time_logged",
}
DISPOSITIONS = vocab.design_dispositions()
UNCERTAINTY_LEVELS = vocab.uncertainty_levels()
CLAIM_CATEGORIES = vocab.claim_categories()
_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,40}$")
AC_PREFIX = {"pt": "CA", "es": "CA", "en": "AC"}


def _obligation_index(run: Run) -> dict[str, dict[str, Any]]:
    """reader obligation ref (``SRC:key``) -> obligation with resolved locator."""
    index: dict[str, dict[str, Any]] = {}
    for src in run.inventory()["sources"]:
        rel = f"stages/reading/{src['id']}.json"
        if not run.path(rel).exists():
            continue
        ledger = run.read(rel)
        for ob in ledger.get("obligations") or []:
            index[f"{src['id']}:{ob['key']}"] = {
                **ob,
                "source_id": src["id"],
                "source_version": src["version"],
            }
    return index


def _evidence_from(ob: dict[str, Any]) -> dict[str, Any]:
    loc = ob["locator"]
    locator: dict[str, Any] = {
        "source_id": ob["source_id"],
        "source_version": ob["source_version"],
        "member": loc["member"],
        "line_start": loc["line_start"],
        "line_end": loc.get("line_end", loc["line_start"]),
        "quote_digest": digest(normalize_for_match(ob["quote"])),
    }
    for extra in ("section", "table", "anchor"):
        if loc.get(extra):
            locator[extra] = str(loc[extra])
    if isinstance(loc.get("page"), int):
        locator["page"] = loc["page"]
    return {"type": "source_locator", "locator": locator, "summary": ob["quote"][:500]}


# ---------------------------------------------------------------------------- claims
def submit_claims(run: Run, payload: Any) -> dict[str, Any]:
    require_stage(run, "reading")
    if run.stage_status("claims") == "complete":
        raise RunError("claims are complete for this run; start a new run to change them")
    errors, compiled = compile_claims(run, payload)
    if errors:
        raise RunError("claims rejected (nothing recorded)", errors)
    run.write_artifact("stages/claims.json", compiled)
    run.save()
    run.state.complete(
        "claims",
        digest([run.artifact_digest(f"stages/reading/{s['id']}.json") for s in run.inventory()["sources"]]),
        str(run.artifact_digest("stages/claims.json")),
    )
    run.write_work_order()
    return {
        "claims": len(compiled["claims"]),
        "decisions": len(compiled["decisions"]),
        "rejected_obligations": len(compiled["rejected"]),
    }


def compile_claims(run: Run, payload: Any) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["claims payload must be an object"], {}
    orch = payload.get("orchestrator")
    if not isinstance(orch, dict) or not orch.get("agent") or not orch.get("model"):
        errors.append("orchestrator.agent and orchestrator.model are required")
    index = _obligation_index(run)
    used: Counter[str] = Counter()
    claims_out: list[dict[str, Any]] = []
    keys: dict[str, str] = {}
    for i, claim in enumerate(payload.get("claims") or []):
        label = f"claims[{i}]"
        key = claim.get("key")
        if not isinstance(key, str) or not _KEY.match(key) or key in keys:
            errors.append(f"{label}: key must be a unique short identifier")
            continue
        refs = claim.get("sources") or []
        if not refs:
            errors.append(f"{label} ({key}): at least one reader obligation ref is required")
        bad = [r for r in refs if r not in index]
        if bad:
            errors.append(f"{label} ({key}): unknown reader obligation refs {bad}")
            continue
        used.update(refs)
        if not str(claim.get("text", "")).strip():
            errors.append(f"{label} ({key}): text is required")
        first = index[refs[0]] if refs else None
        anchor = {"run": run.run_id, "key": key}
        if first:
            anchor.update(
                source=first["source_id"],
                member=first["locator"]["member"],
                line=str(first["locator"]["line_start"]),
            )
        cid = derive("claim", anchor)
        keys[key] = cid
        uncertainty = claim.get("uncertainty") or {"level": "confirmed"}
        if isinstance(uncertainty, str):
            uncertainty = {"level": uncertainty}
        # Regression (dogfood c05): validate here, never store a shape the design stage will refuse.
        extra = (
            sorted(set(uncertainty) - {"level", "note"})
            if isinstance(uncertainty, dict)
            else ["<not an object>"]
        )
        if extra:
            errors.append(f"{label} ({key}): uncertainty accepts only level and note; put {extra} in note")
        elif uncertainty.get("level") not in UNCERTAINTY_LEVELS:
            errors.append(f"{label} ({key}): uncertainty.level must be one of {sorted(UNCERTAINTY_LEVELS)}")
        if claim.get("category", "functional") not in CLAIM_CATEGORIES:
            errors.append(f"{label} ({key}): category must be one of {sorted(CLAIM_CATEGORIES)}")
        unknown_fields = sorted(set(claim) - {"key", "text", "category", "sources", "uncertainty"})
        if unknown_fields:
            errors.append(f"{label} ({key}): unknown fields {unknown_fields}")
        claims_out.append(
            {
                "id": cid,
                "key": key,
                "text": str(claim.get("text", "")).strip(),
                "category": claim.get("category", "functional"),
                "evidence": [_evidence_from(index[r]) for r in refs],
                "uncertainty": uncertainty,
                "temporal": {"status": "effective"},
                "disposition": {"status": "UNASSESSED"},
                "reader_refs": refs,
            }
        )
    rejected = payload.get("rejected") or []
    for i, rej in enumerate(rejected):
        if rej.get("ref") not in index or not str(rej.get("reason", "")).strip():
            errors.append(f"rejected[{i}]: needs a known ref and a reason")
        else:
            used[rej["ref"]] += 1
    missing = sorted(set(index) - set(used))
    if missing:
        errors.append(
            f"reader obligations not accounted for (merge into a claim or reject with reason): {missing}"
        )
    dup = sorted(r for r, n in used.items() if n > 1)
    if dup:
        errors.append(f"reader obligations accounted for more than once: {dup}")

    decisions_out: list[dict[str, Any]] = []
    by_key = {c["key"]: c for c in claims_out}
    for i, dec in enumerate(payload.get("decisions") or []):
        label = f"decisions[{i}]"
        key = dec.get("key")
        if not isinstance(key, str) or not _KEY.match(key) or key in keys:
            errors.append(f"{label}: key must be a unique short identifier")
            continue
        refs = dec.get("sources") or []
        if not refs or any(r not in index for r in refs):
            errors.append(
                f"{label} ({key}): decisions must cite reader obligation refs from a decision source"
            )
            continue
        status = dec.get("status")
        if status not in ("approved", "proposed", "rejected"):
            errors.append(
                f"{label} ({key}): status must be approved, proposed or rejected as stated by the source"
            )
            continue
        did = derive("decision", {"run": run.run_id, "key": key})
        keys[key] = did
        supersedes = dec.get("supersedes") or []
        for target in supersedes:
            if target not in by_key:
                errors.append(f"{label} ({key}): supersedes unknown claim key {target}")
            elif status != "approved":
                errors.append(f"{label} ({key}): only an approved decision may supersede claims")
            else:
                c = by_key[target]
                c["temporal"] = {
                    "status": "superseded",
                    "superseded_by": [did],
                    "superseded_reason": str(dec.get("text", ""))[:300],
                }
                c["disposition"] = {"status": "SUPERSEDED", "rationale": f"Superseded by decision {key}."}
        decisions_out.append(
            {
                "id": did,
                "key": key,
                "text": str(dec.get("text", "")),
                "status": status,
                "supersedes_claims": [by_key[t]["id"] for t in supersedes if t in by_key],
                "evidence": [_evidence_from(index[r]) for r in refs],
            }
        )
        used.update(refs)  # decision evidence may reuse obligation refs already merged
    compiled = {
        "orchestrator": orch,
        "claims": claims_out,
        "decisions": decisions_out,
        "rejected": rejected,
        "conflicts": payload.get("conflicts") or [],
        "keys": keys,
    }
    return errors, compiled


# ---------------------------------------------------------------------------- design
def submit_design(run: Run, payload: Any) -> dict[str, Any]:
    require_stage(run, "claims")
    if run.stage_status("design") == "complete":
        raise RunError(
            "design is complete for this run; refinement of an existing design is a later milestone"
        )
    errors, backlog = compile_design(run, payload)
    if errors:
        raise RunError("design rejected (nothing recorded)", errors)
    run.write_artifact("stages/design.json", payload)
    run.write_artifact("stages/backlog.draft.json", backlog)
    run.save()
    run.state.complete(
        "design",
        str(run.artifact_digest("stages/claims.json")),
        str(run.artifact_digest("stages/backlog.draft.json")),
    )
    run.write_work_order()
    return {
        "items": len(backlog["items"]),
        "criteria": len(backlog["criteria"]),
        "relations": len(backlog["relations"]),
        "questions": len(backlog["questions"]),
    }


def _templated(texts: list[tuple[str, str]], label: str) -> list[str]:
    """Reject >= 3 entries whose text is identical once digits and identifiers are masked (FTD idea)."""
    masked: dict[str, list[str]] = {}
    for key, text in texts:
        norm = re.sub(r"\d+", "#", normalize_for_match(text))
        if len(norm) >= 12:
            masked.setdefault(norm, []).append(key)
    return [
        f"templated {label}: {keys} share the same text; write each from its own claims"
        for keys in masked.values()
        if len(keys) >= 3
    ]


def compile_design(run: Run, payload: Any) -> tuple[list[str], dict[str, Any]]:
    if not isinstance(payload, dict):
        return ["design payload must be an object"], {}
    errors: list[str] = []
    request = run.request()
    language = request["language"]
    levels = set(request["levels"])
    claims_doc = run.read("stages/claims.json")
    claim_by_key = {c["key"]: c for c in claims_doc["claims"]}
    designer = payload.get("designer")
    if not isinstance(designer, dict) or not designer.get("agent") or not designer.get("model"):
        errors.append("designer.agent and designer.model are required")

    keys: dict[str, str] = {}
    items_in = payload.get("items") or []
    crits_in = payload.get("criteria") or []
    for coll, kind_of in ((items_in, None), (crits_in, "criterion")):
        for entry in coll:
            key = entry.get("key")
            if not isinstance(key, str) or not _KEY.match(key) or key in keys or key in claim_by_key:
                errors.append(f"invalid or duplicate key {key!r}")
                continue
            kind = kind_of or entry.get("type")
            if kind not in TYPE_LEVEL and kind != "criterion":
                errors.append(f"{key}: unknown type {entry.get('type')!r}")
                continue
            keys[key] = derive(str(kind), {"run": run.run_id, "key": key})
    if errors:
        return errors, {}

    def claim_ids(entry_key: str, refs: Any) -> list[str]:
        out = []
        for ref in refs or []:
            if ref not in claim_by_key:
                errors.append(f"{entry_key}: unknown claim key {ref}")
            else:
                out.append(claim_by_key[ref]["id"])
        return out

    items: list[dict[str, Any]] = []
    for entry in items_in:
        key, itype = entry["key"], entry["type"]
        if TYPE_LEVEL[itype] not in levels:
            errors.append(f"{key}: {itype} is outside the requested levels {sorted(levels)}")
        content = entry.get("content")
        content_errors = validate_content(content)
        if content_errors:
            errors.extend(f"{key}: {e}" for e in content_errors)
            continue
        if content["kind"] not in TYPE_CONTENT[itype]:
            errors.append(f"{key}: content kind {content['kind']} does not fit a {itype}")
            continue
        parent = entry.get("parent")
        if parent is not None and parent not in keys:
            errors.append(f"{key}: parent {parent} is not a design key")
        try:
            html = description_html(content, language)
        except RichTextError as exc:  # pragma: no cover - validated above
            errors.append(f"{key}: {exc}")
            continue
        item: dict[str, Any] = {
            "id": keys[key],
            "key": key,
            "type": itype,
            "title": str(entry.get("title", "")).strip(),
            "parent": keys.get(parent) if parent else None,
            "claim_refs": claim_ids(key, entry.get("claims")),
            "origin": entry.get("origin", "generated"),
            "status": "draft",
            "content": content,
            "description": {"format": "html", "value": html, "language": language},
        }
        if not item["title"]:
            errors.append(f"{key}: title is required")
        if entry.get("technical_rationale"):
            item["technical_rationale"] = str(entry["technical_rationale"])
        if itype in ("story", "enabler", "spike", "bug"):
            item["acceptance_style"] = entry.get("acceptance_style", request["acceptance_style"])
        if content["kind"] in STORY_FORMAT:
            item["story_format"] = STORY_FORMAT[content["kind"]]
        fields = entry.get("fields") or {}
        bad = sorted(set(fields) & FORBIDDEN_FIELDS)
        if bad:
            errors.append(
                f"{key}: fields {bad} are never generated (no invented assignments, dates or effort)"
            )
        unknown = sorted(set(fields) - ALLOWED_FIELDS - FORBIDDEN_FIELDS)
        if unknown:
            errors.append(f"{key}: unknown fields {unknown}")
        out_fields = {}
        for name, value in fields.items():
            if name not in ALLOWED_FIELDS or not isinstance(value, dict):
                continue
            fv = {k: v for k, v in value.items() if k in ("state", "value", "unit", "scale", "rationale")}
            fv.setdefault("review_status", "unreviewed")
            if value.get("claims"):
                fv["evidence"] = [
                    ev
                    for ref in value["claims"]
                    if ref in claim_by_key
                    for ev in claim_by_key[ref]["evidence"]
                ]
            out_fields[name] = fv
        if out_fields:
            item["fields"] = out_fields
        items.append(item)

    item_type = {i["id"]: i["type"] for i in items}
    criteria: list[dict[str, Any]] = []
    per_parent: Counter[str] = Counter()
    prefix = AC_PREFIX.get(language.split("-")[0], "AC")
    if crits_in and "acceptance" not in levels:
        errors.append("acceptance criteria are outside the requested levels")
    for entry in crits_in:
        key = entry["key"]
        parent = keys.get(entry.get("parent", ""))
        if parent is None or parent not in item_type:
            errors.append(f"{key}: parent {entry.get('parent')} is not a design item")
            continue
        per_parent[parent] += 1
        crit: dict[str, Any] = {
            "id": keys[key],
            "key": key,
            "parent": parent,
            "visible_id": f"{prefix}-{per_parent[parent]:02d}",
            "order": per_parent[parent] - 1,
            "style": entry.get("style", request["acceptance_style"]),
            "expected_outcomes": [str(o) for o in entry.get("expected_outcomes") or []],
            "claim_refs": claim_ids(key, entry.get("claims")),
            "origin": entry.get("origin", "generated"),
            "status": entry.get("status", "confirmed"),
        }
        for opt in ("text", "condition", "trigger", "rationale", "verification_approach"):
            if entry.get(opt):
                crit[opt] = str(entry[opt])
        if entry.get("exceptions"):
            crit["exceptions"] = [str(x) for x in entry["exceptions"]]
        if crit["status"] == "proposed" and crit["origin"] == "generated":
            crit["origin"] = "proposed"
        criteria.append(crit)

    relations = []
    for i, rel in enumerate(payload.get("relations") or []):
        src, tgt = keys.get(rel.get("source", "")), keys.get(rel.get("target", ""))
        if src is None or tgt is None:
            errors.append(f"relations[{i}]: source/target must be design keys")
            continue
        if "dependencies" not in levels:
            errors.append("relations are outside the requested levels (dependencies)")
            break
        relations.append(
            {
                "id": derive(
                    "relation",
                    {"run": run.run_id, "key": f"{rel['source']}>{rel['target']}:{rel.get('type')}"},
                ),
                "type": rel.get("type", "predecessor"),
                "source": src,
                "target": tgt,
                "status": rel.get("status", "proposed"),
                "confidence": rel.get("confidence", "medium"),
                "reason": str(rel.get("reason", "")).strip() or "missing reason",
            }
        )
        if not str(rel.get("reason", "")).strip():
            errors.append(f"relations[{i}]: reason is required")

    all_keys = {**keys, **{k: v["id"] for k, v in claim_by_key.items()}, **claims_doc.get("keys", {})}
    questions = []
    for i, q in enumerate(payload.get("questions") or []):
        key = q.get("key") or f"Q{i + 1}"
        affects = [all_keys[a] for a in q.get("affects") or [] if a in all_keys]
        unknown_affects = [a for a in q.get("affects") or [] if a not in all_keys]
        if unknown_affects:
            errors.append(f"questions[{i}]: unknown affected keys {unknown_affects}")
        questions.append(
            {
                "id": derive("question", {"run": run.run_id, "key": key}),
                "key": key,
                "text": str(q.get("text", "")),
                "impact": str(q.get("impact", "")),
                "alternatives": [str(a) for a in q.get("alternatives") or []],
                "blocking": bool(q.get("blocking", False)),
                "affects": sorted(set(affects)),
                "status": "open",
            }
        )

    # Dispositions: every effective claim exactly once.
    dispositions = {d.get("claim"): d for d in payload.get("dispositions") or []}
    for ckey, claim in claim_by_key.items():
        if claim["temporal"]["status"] == "superseded":
            if ckey in dispositions:
                errors.append(f"{ckey}: superseded claims are dispositioned by their decision")
            continue
        disp = dispositions.get(ckey)
        if disp is None:
            errors.append(
                f"claim {ckey}: disposition required (COVERED, NOT_COVERED, QUESTION_REQUIRED, ...)"
            )
            continue
        status = disp.get("status")
        if status not in DISPOSITIONS:
            errors.append(f"claim {ckey}: disposition status must be one of {sorted(DISPOSITIONS)}")
            continue
        covered = [keys[k] for k in disp.get("covered_by") or [] if k in keys]
        if len(covered) != len(disp.get("covered_by") or []):
            errors.append(f"claim {ckey}: covered_by must reference design keys")
        claim["disposition"] = {"status": status, "rationale": str(disp.get("rationale", "")).strip() or "—"}
        if covered:
            claim["disposition"]["covered_by"] = covered
    extra = sorted(set(dispositions) - set(claim_by_key))
    if extra:
        errors.append(f"dispositions for unknown claims {extra}")

    errors += _templated(
        [(i["key"], i["description"]["value"]) for i in items if i["type"] != "epic"], "items"
    )
    errors += _templated(
        [(c["key"], " ".join(c["expected_outcomes"]) + c.get("text", "")) for c in criteria], "criteria"
    )
    if errors:
        return errors, {}

    sources = []
    for src in run.inventory()["sources"]:
        rec = {k: v for k, v in src.items() if k != "members_text"}
        rel = f"stages/reading/{src['id']}.json"
        ledger = run.read(rel) if run.path(rel).exists() else {"members": []}
        statuses = {m["path"]: m["status"] for m in ledger["members"]}
        for member in rec.get("members", []):
            st = statuses.get(member["path"])
            if st in ("read", "partial", "unreadable", "skipped"):
                member["status"] = st
        all_read = rec.get("members") and all(m["status"] == "read" for m in rec["members"])
        rec["read_status"] = "complete" if all_read else ("partial" if statuses else "not_read")
        sources.append(rec)
    backlog = {
        "schema_version": SCHEMA_VERSION,
        "kind": "pbd.backlog",
        "run_id": run.run_id,
        "language": language,
        "synthetic": bool(request.get("synthetic")),
        "profile": request["profile"],
        "sources": sources,
        "claims": [
            {k: v for k, v in c.items() if k not in ("key", "reader_refs")} for c in claim_by_key.values()
        ],
        "items": [{k: v for k, v in i.items() if k != "key"} for i in items],
        "criteria": [{k: v for k, v in c.items() if k != "key"} for c in criteria],
        "relations": relations,
        "questions": [{k: v for k, v in q.items() if k != "key"} for q in questions],
        "decisions": [{k: v for k, v in d.items() if k != "key"} for d in claims_doc["decisions"]],
        "findings": [],
    }
    issues = validate("backlog", backlog) or check_backlog(backlog)
    if issues:
        reverse = {v: k for k, v in all_keys.items()}

        def humanize(text: str) -> str:
            return re.sub(r"PBD-[A-Z]+-[0-9A-Z]{12}", lambda m: reverse.get(m.group(0), m.group(0)), text)

        return [humanize(str(i)) for i in issues], {}
    backlog["keys"] = {
        **{v: k for k, v in keys.items()},
        **{c["id"]: k for k, c in claim_by_key.items()},
        **{q["id"]: q["key"] for q in questions},
        **{d["id"]: d["key"] for d in claims_doc["decisions"]},
    }
    return [], backlog


def content_kinds() -> list[str]:
    return sorted(CONTENT_KINDS)
