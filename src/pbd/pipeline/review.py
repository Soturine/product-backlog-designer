"""Independent, source-first review submission.

The reviewer re-reads the original sources BEFORE looking at the generated backlog and records
its own obligation inventory (each with a verified quote). That inventory is the independent
denominator for coverage gates; it is never derived from the generated claims. The reviewer then
judges every work item and every acceptance criterion exactly once.
"""

from __future__ import annotations

from typing import Any

from pbd import vocab
from pbd.core.canonical import digest
from pbd.pipeline.reading import normalize_for_match
from pbd.pipeline.run import Run, RunError, require_stage

VERDICTS = vocab.VERDICTS
SUPPORT = vocab.SOURCE_SUPPORT
INVEST = vocab.INVEST_DIMENSIONS
RATINGS = vocab.INVEST_RATINGS
OB_DISPOSITIONS = vocab.review_dispositions()
CLASSIFICATIONS = vocab.finding_classifications()
SEVERITIES = vocab.finding_severities()
GATES_REVIEWED = {"G02", "G04", "G05", "G06", "G07", "G08", "G09", "G13", "G14"}


def _source_lines(run: Run, review: dict[str, Any] | None = None) -> dict[tuple[str, str], list[str]]:
    """Extracted lines per member; visual members only through the REVIEWER'S own transcription."""
    out = {}
    own = (review or {}).get("visual_transcriptions") or {}
    for src in run.inventory()["sources"]:
        for m in src["members_text"]:
            if m.get("readable"):
                out[(src["id"], m["path"])] = run.path(m["text_ref"]).read_text(encoding="utf-8").splitlines()
            elif m.get("visual"):
                text = own.get(f"{src['id']}/{m['path']}") if isinstance(own, dict) else None
                if isinstance(text, str) and text.strip():
                    out[(src["id"], m["path"])] = text.splitlines()
    return out


def validate_review(run: Run, review: Any) -> list[str]:
    if not isinstance(review, dict):
        return ["review must be an object"]
    errors: list[str] = []
    design = run.read("stages/design.json")
    claims = run.read("stages/claims.json")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict) or not reviewer.get("agent") or not reviewer.get("model"):
        errors.append("reviewer.agent and reviewer.model (actual model) are required")
        reviewer = {}
    builders = {
        str(design.get("designer", {}).get("agent")),
        str(claims.get("orchestrator", {}).get("agent")),
    }
    independence = reviewer.get("independence")
    if independence not in ("separate_agent", "sequential_role"):
        errors.append("reviewer.independence must be separate_agent or sequential_role")
    elif independence == "separate_agent" and str(reviewer.get("agent")) in builders:
        errors.append("reviewer claims separate_agent but is the same agent that reconciled or designed")

    sources = {s["id"] for s in run.inventory()["sources"]}
    reread = {r.get("source_id") for r in review.get("sources_reread") or [] if isinstance(r, dict)}
    if reread != sources:
        errors.append(f"sources_reread must list every source of the run; missing {sorted(sources - reread)}")

    lines = _source_lines(run, review)
    design_keys = {i["key"] for i in design.get("items", [])} | {c["key"] for c in design.get("criteria", [])}
    claim_keys = {c["key"] for c in claims["claims"]}
    obligations = review.get("independent_obligations") or []
    if not obligations:
        errors.append("independent_obligations is required (the reviewer's own inventory from the sources)")
    seen: set[str] = set()
    for i, ob in enumerate(obligations):
        label = f"independent_obligations[{i}]"
        key = ob.get("key")
        if not key or key in seen:
            errors.append(f"{label}: unique key required")
        seen.add(str(key))
        loc = ob.get("locator") or {}
        text_lines = lines.get((str(loc.get("source_id")), str(loc.get("member"))))
        start, end = loc.get("line_start"), loc.get("line_end", loc.get("line_start"))
        if text_lines is None:
            errors.append(f"{label}: locator must name a readable source_id and member")
        elif not (isinstance(start, int) and isinstance(end, int) and 1 <= start <= end <= len(text_lines)):
            errors.append(f"{label}: lines {start}-{end} outside the member")
        elif (
            normalize_for_match(str(ob.get("quote", "")))
            not in normalize_for_match(" ".join(text_lines[start - 1 : end]))
            or len(str(ob.get("quote", "")).strip()) < 3
        ):
            errors.append(f"{label}: quote not found in the cited lines")
        if ob.get("disposition") not in OB_DISPOSITIONS:
            errors.append(f"{label}: disposition must be one of {sorted(OB_DISPOSITIONS)}")
        bad = [k for k in ob.get("matched_claims") or [] if k not in claim_keys]
        bad += [k for k in ob.get("covered_by") or [] if k not in design_keys]
        if bad:
            errors.append(f"{label}: unknown keys {bad}")
        if ob.get("disposition") in ("COVERED", "PARTIALLY_COVERED") and not ob.get("covered_by"):
            errors.append(f"{label}: {ob.get('disposition')} requires covered_by")
        if not str(ob.get("rationale", "")).strip():
            errors.append(f"{label}: rationale required")

    for kind, expected in (
        ("items", [i["key"] for i in design.get("items", [])]),
        ("criteria", [c["key"] for c in design.get("criteria", [])]),
    ):
        entries = review.get(kind) or []
        keys = [e.get("key") for e in entries]
        missing = sorted(set(expected) - set(keys))
        extra = sorted(set(keys) - set(expected))
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if missing or extra or dupes:
            errors.append(
                f"{kind}: every design entry must be reviewed exactly once "
                f"(missing {missing}, unknown {extra}, duplicated {dupes})"
            )
        types = {i["key"]: i["type"] for i in design.get("items", [])}
        for e in entries:
            if e.get("verdict") not in VERDICTS:
                errors.append(f"{kind} {e.get('key')}: verdict must be pass, concern or fail")
            if e.get("source_support") not in SUPPORT:
                errors.append(f"{kind} {e.get('key')}: source_support must be one of {sorted(SUPPORT)}")
            if e.get("verdict") in ("concern", "fail") and not str(e.get("notes", "")).strip():
                errors.append(f"{kind} {e.get('key')}: a concern or fail needs notes")
            if (
                e.get("task_sufficiency") is not None
                and e.get("task_sufficiency") not in vocab.TASK_SUFFICIENCY
            ):
                errors.append(
                    f"{kind} {e.get('key')}: task_sufficiency must be sufficient, insufficient"
                    " or not_applicable"
                )
            if kind == "items" and types.get(e.get("key")) == "story":
                invest = e.get("invest") or {}
                for dim in INVEST:
                    rating = (
                        (invest.get(dim) or {}).get("rating") if isinstance(invest.get(dim), dict) else None
                    )
                    if rating not in RATINGS:
                        errors.append(
                            f"story {e.get('key')}: invest.{dim}.rating must be one of {sorted(RATINGS)}"
                        )
    for i, f in enumerate(review.get("findings") or []):
        label = f"findings[{i}]"
        if f.get("classification") not in CLASSIFICATIONS or f.get("severity") not in SEVERITIES:
            errors.append(f"{label}: classification and severity are required")
        for field in ("expected", "actual", "why", "impact", "recommendation"):
            if not str(f.get(field, "")).strip():
                errors.append(f"{label}: {field} is required")
        bad = [k for k in f.get("affects") or [] if k not in design_keys | claim_keys]
        if bad or not f.get("affects"):
            errors.append(f"{label}: affects must list design or claim keys (unknown {bad})")
        if f.get("review_status", "confirmed") not in vocab.REVIEW_FINDING_STATUS:
            errors.append(f"{label}: review_status must be candidate or confirmed")
        if f.get("gate") and f["gate"] not in GATES_REVIEWED:
            errors.append(f"{label}: gate must be one of {sorted(GATES_REVIEWED)}")
    for i, d in enumerate(review.get("duplicates") or []):
        if d.get("assessment") not in vocab.DUPLICATE_ASSESSMENTS or not d.get("rationale"):
            errors.append(
                f"duplicates[{i}]: assessment (duplicate, distinct or overlap) and rationale required"
            )
    return errors


def submit_review(run: Run, review: dict[str, Any]) -> dict[str, Any]:
    require_stage(run, "design")
    if run.stage_status("independent_review") == "complete":
        raise RunError("independent review already recorded for this run")
    errors = validate_review(run, review)
    if errors:
        raise RunError("review rejected (nothing recorded)", errors)
    run.write_artifact("stages/review.json", review)
    indep = review["reviewer"]["independence"]
    run.state.manifest["status"]["semantic_review"] = (
        "independent_complete" if indep == "separate_agent" else "self_review_only"
    )
    if indep != "separate_agent":
        run.state.manifest["limitations"].append(
            "independent review ran as a sequential role in the same agent (reduced independence)"
        )
    run.save()
    run.state.complete(
        "independent_review",
        digest([run.artifact_digest("stages/backlog.draft.json")]),
        str(run.artifact_digest("stages/review.json")),
    )
    run.write_work_order()
    return {
        "obligations": len(review["independent_obligations"]),
        "findings": len(review.get("findings") or []),
    }
