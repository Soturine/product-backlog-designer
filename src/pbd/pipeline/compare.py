"""Compare mode: two imported backlogs judged against the same sources.

The comparison is semantic and agent-led. The reviewer re-reads the sources, builds its own
obligation inventory and, for every obligation, records the disposition of EACH side
(``left``/``right``) with the items/criteria that carry it. It reviews every item and criterion of
both sides once and maps them many-to-many (1:1, 1:N, N:1, N:N) with a relation and rationale.
Neither backlog is gold, item counts are never a quality score and no winner is computed.

The runtime validates quotes, keys and completeness, derives cardinalities, unmatched entries and
per-side coverage over the shared denominator, and writes ``output/comparison.json`` + Markdown.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pbd import __version__
from pbd.core.canonical import digest
from pbd.pipeline.audit import DRAFTS
from pbd.pipeline.review import (
    _check_entry,
    _check_obligation,
    _check_reread,
    _check_reviewer,
    _source_lines,
)
from pbd.pipeline.run import Run, RunError, require_stage
from pbd.validation.invariants import check_backlog

SIDES = ("left", "right")
RELATIONS = {"equivalent", "split", "merge", "overlap", "divergent", "conflicting"}
SIDE_SCOPES = {"left", "right", "both"}


def _design_sides(run: Run) -> dict[str, Any]:
    design = run.read("stages/design.json")
    if design.get("mode") != "compare":
        raise RunError("this run is not a comparison (start with --mode compare and two --baseline)")
    sides: dict[str, Any] = design["sides"]
    return sides


def _side_keys(sides: dict[str, Any]) -> dict[str, dict[str, set[str]]]:
    return {
        s: {
            "items": {i["key"] for i in sides[s]["items"]},
            "criteria": {c["key"] for c in sides[s]["criteria"]},
        }
        for s in SIDES
    }


def _check_obligations(
    run: Run, payload: dict[str, Any], claim_keys: set[str], keys: dict[str, dict[str, set[str]]]
) -> list[str]:
    obligations = payload.get("independent_obligations") or []
    if not obligations:
        return ["independent_obligations is required (the reviewer's own inventory from the sources)"]
    lines = _source_lines(run, payload)
    errors: list[str] = []
    seen: set[str] = set()
    for i, ob in enumerate(obligations):
        label = f"independent_obligations[{i}]"
        if not ob.get("key") or ob.get("key") in seen:
            errors.append(f"{label}: unique key required")
        seen.add(str(ob.get("key")))
        for side in SIDES:
            part = ob.get(side)
            if not isinstance(part, dict):
                errors.append(f"{label}: {side} disposition object required")
                continue
            merged = {**ob, **part}
            side_keys = keys[side]["items"] | keys[side]["criteria"]
            for e in _check_obligation(label, merged, lines, claim_keys, side_keys):
                # the quote and locator are shared: report them once, under the left side
                shared = e.startswith(f"{label}: quote") or "locator" in e or "lines " in e
                if side == "left" or not shared:
                    errors.append(e.replace(label, f"{label}.{side}", 1))
    return errors


def _check_reviews(payload: dict[str, Any], sides: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for kind in ("items", "criteria"):
        expected = [e["key"] for s in SIDES for e in sides[s][kind]]
        types = {i["key"]: i["type"] for s in SIDES for i in sides[s]["items"]}
        entries = payload.get(kind) or []
        got = [e.get("key") for e in entries]
        missing = sorted(set(expected) - set(got))
        extra = sorted({str(k) for k in got} - set(expected))
        dupes = sorted({str(k) for k in got if got.count(k) > 1})
        if missing or extra or dupes:
            errors.append(
                f"{kind}: every entry of both baselines must be reviewed exactly once "
                f"(missing {missing}, unknown {extra}, duplicated {dupes})"
            )
        for e in entries:
            errors += _check_entry(kind, e, types.get(e.get("key")))
    return errors


def _check_mappings(payload: dict[str, Any], keys: dict[str, dict[str, set[str]]]) -> list[str]:
    errors = []
    for i, m in enumerate(payload.get("mappings") or []):
        label = f"mappings[{i}]"
        for side in SIDES:
            refs = m.get(side) or []
            allowed = keys[side]["items"] | keys[side]["criteria"]
            bad = [r for r in refs if r not in allowed]
            if not refs or bad:
                errors.append(f"{label}: {side} must list keys of the {side} baseline (unknown {bad})")
        if m.get("relation") not in RELATIONS:
            errors.append(f"{label}: relation must be one of {sorted(RELATIONS)}")
        if not str(m.get("rationale", "")).strip():
            errors.append(f"{label}: rationale required")
    return errors


def _check_findings(payload: dict[str, Any], known: set[str]) -> list[str]:
    from pbd.pipeline.review import _check_findings as review_findings

    errors = review_findings({"findings": payload.get("findings") or []}, known)
    for i, f in enumerate(payload.get("findings") or []):
        if f.get("side") not in SIDE_SCOPES:
            errors.append(f"findings[{i}]: side must be left, right or both")
    return errors


def validate_comparison(run: Run, payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["comparison must be an object"]
    sides = _design_sides(run)
    design = run.read("stages/design.json")
    claims = run.read("stages/claims.json")
    claim_keys = {c["key"] for c in claims["claims"]}
    keys = _side_keys(sides)
    known = claim_keys | {k for s in SIDES for group in keys[s].values() for k in group}
    return [
        *_check_reviewer(run, payload, design, claims),
        *_check_reread(run, payload),
        *_check_obligations(run, payload, claim_keys, keys),
        *_check_reviews(payload, sides),
        *_check_mappings(payload, keys),
        *_check_findings(payload, known),
    ]


def submit_comparison(run: Run, payload: dict[str, Any]) -> dict[str, Any]:
    require_stage(run, "design")
    if run.stage_status("independent_review") == "complete":
        raise RunError("comparison already recorded for this run")
    errors = validate_comparison(run, payload)
    if errors:
        raise RunError("comparison rejected (nothing recorded)", errors)
    run.write_artifact("stages/review.json", payload)
    indep = payload["reviewer"]["independence"]
    run.state.manifest["status"]["semantic_review"] = (
        "independent_complete" if indep == "separate_agent" else "self_review_only"
    )
    if indep != "separate_agent":
        run.state.manifest["limitations"].append(
            "comparison ran as a sequential role in the same agent (reduced independence)"
        )
    run.save()
    run.state.complete(
        "independent_review",
        digest([run.artifact_digest(DRAFTS[s]) for s in SIDES]),
        str(run.artifact_digest("stages/review.json")),
    )
    run.write_work_order()
    return {
        "obligations": len(payload["independent_obligations"]),
        "mappings": len(payload.get("mappings") or []),
        "findings": len(payload.get("findings") or []),
    }


def _cardinality(m: dict[str, Any]) -> str:
    left, right = len(m["left"]), len(m["right"])
    return f"{'1' if left == 1 else 'N'}:{'1' if right == 1 else 'N'}"


def build_comparison(run: Run) -> dict[str, Any]:
    sides = _design_sides(run)
    review = run.read("stages/review.json")
    obligations = review["independent_obligations"]
    total = len(obligations)
    drafts = {s: run.read(DRAFTS[s]) for s in SIDES}
    mapped: dict[str, set[str]] = {s: set() for s in SIDES}
    mappings = []
    for m in review.get("mappings") or []:
        for s in SIDES:
            mapped[s].update(m[s])
        mappings.append({**m, "cardinality": _cardinality(m)})
    verdicts = {e["key"]: e for e in review.get("items", []) + review.get("criteria", [])}
    out_sides = {}
    for s in SIDES:
        disp = Counter(o[s]["disposition"] for o in obligations)
        structural = [str(i) for i in check_backlog({k: v for k, v in drafts[s].items() if k != "keys"})]
        out_sides[s] = {
            "baseline": sides[s]["baseline"],
            "items": {
                "total": len(sides[s]["items"]),
                "by_type": dict(sorted(Counter(i["type"] for i in sides[s]["items"]).items())),
            },
            "criteria": len(sides[s]["criteria"]),
            "coverage": {
                "denominator": total,
                "provenance": "independent reviewer inventory (shared by both sides)",
                "covered": disp["COVERED"],
                "partially_covered": disp["PARTIALLY_COVERED"],
                "not_covered": disp["NOT_COVERED"],
                "breakdown": dict(sorted(disp.items())),
            },
            "unsupported": sorted(
                k
                for k in {e["key"] for e in sides[s]["items"]} | {e["key"] for e in sides[s]["criteria"]}
                if verdicts.get(k, {}).get("source_support") == "unsupported"
            ),
            "unmatched_items": sorted({i["key"] for i in sides[s]["items"]} - mapped[s]),
            "structural_issues": structural,
        }
    per_obligation = [
        {
            "key": o["key"],
            "text": o["text"],
            "quote": o["quote"],
            "locator": o["locator"],
            "left": o["left"],
            "right": o["right"],
            "agreement": "same" if o["left"]["disposition"] == o["right"]["disposition"] else "differs",
        }
        for o in obligations
    ]
    return {
        "kind": "pbd.comparison",
        "run_id": run.run_id,
        "validator_version": __version__,
        "language": run.request()["language"],
        "reviewer": review["reviewer"],
        "sides": out_sides,
        "obligations": per_obligation,
        "mappings": mappings,
        "mapping_cardinality": dict(sorted(Counter(m["cardinality"] for m in mappings).items())),
        "findings": review.get("findings") or [],
        "item_reviews": review.get("items", []),
        "criterion_reviews": review.get("criteria", []),
        "notes": [
            "Neither baseline is treated as gold; coverage on both sides uses the same reviewer inventory.",
            "Item counts are not a quality measure and no winner is computed.",
            "Quality gates apply to a single backlog: audit each baseline to obtain its gates.",
        ],
        "limitations": run.state.manifest["limitations"],
    }


def comparison_markdown(doc: dict[str, Any]) -> str:
    lines = ["# Comparison", ""]
    for s in SIDES:
        side = doc["sides"][s]
        cov = side["coverage"]
        lines += [
            f"## {s}: {side['baseline']['source_file']}",
            f"- items: {side['items']['total']} {side['items']['by_type']}; criteria: {side['criteria']}",
            f"- covered {cov['covered']}/{cov['denominator']}, partial {cov['partially_covered']}/"
            f"{cov['denominator']}, not covered {cov['not_covered']}/{cov['denominator']}",
            f"- unmatched items: {', '.join(side['unmatched_items']) or '-'}",
            f"- unsupported: {', '.join(side['unsupported']) or '-'}",
            "",
        ]
    lines += ["## Mappings", ""]
    for m in doc["mappings"]:
        lines.append(
            f"- {', '.join(m['left'])} ↔ {', '.join(m['right'])} ({m['relation']}, {m['cardinality']}): "
            f"{m['rationale']}"
        )
    lines += ["", "## Obligations", ""]
    for o in doc["obligations"]:
        lines.append(
            f"- {o['key']}: left {o['left']['disposition']}, right {o['right']['disposition']} — {o['text']}"
        )
    lines += ["", "## Findings", ""]
    for f in doc["findings"]:
        lines.append(
            f"- [{f['severity']}] ({f['side']}) {f['expected']} / {f['actual']} → {f['recommendation']}"
        )
    return "\n".join(lines) + "\n"


def finalize_comparison(run: Run) -> dict[str, Any]:
    require_stage(run, "independent_review")
    if run.stage_status("render") == "complete":
        raise RunError("run already finalized")
    doc = build_comparison(run)
    run.write_artifact("output/comparison.json", doc)
    run.write_artifact(
        "output/comparison.md", data=comparison_markdown(doc).encode("utf-8"), media_type="text/markdown"
    )
    run.save()
    cmp_digest = str(run.artifact_digest("output/comparison.json"))
    run.state.complete("checks", str(run.artifact_digest("stages/review.json")), cmp_digest)
    run.state.complete("gates", cmp_digest, cmp_digest)
    from pbd.render.report_html import render_comparison_report

    html = render_comparison_report(doc, run.request().get("title"), __version__)
    run.write_artifact("output/report.html", data=html.encode("utf-8"), media_type="text/html")
    status = run.state.manifest["status"]
    status["run"] = "complete"
    status["publication_readiness"] = "not_applicable"
    status["remote_state"] = "not_contacted"
    run.save()
    run.state.complete("render", cmp_digest, str(run.artifact_digest("output/report.html")))
    run.write_work_order()
    return {
        "run_id": run.run_id,
        "report": str(run.path("output/report.html")),
        "comparison": str(run.path("output/comparison.json")),
        "mappings": len(doc["mappings"]),
        "coverage": {s: doc["sides"][s]["coverage"] for s in SIDES},
    }
