"""Compute G01-G18 for a run from recorded evidence.

Deterministic results come from ``checks`` (written to ``output/checks.json`` during the checks
stage); semantic results come from the independent review (``stages/review.json``). Every PASS
cites those artifacts with run, stage and digest so ``verify_gate_report`` can re-derive them.
Anything without evidence is NOT_RUN, BLOCKED or NOT_APPLICABLE with a reason, never PASS.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pbd import SCHEMA_VERSION, __version__
from pbd.pipeline.run import Run
from pbd.validation.gates import GATES

CHECKS = "output/checks.json"
REVIEW = "stages/review.json"
INVENTORY = "sources/inventory.json"
_BREAKDOWN = {
    "COVERED": "covered",
    "PARTIALLY_COVERED": "partially_covered",
    "NOT_COVERED": "not_covered",
    "QUESTION_REQUIRED": "question_required",
    "CONFLICTING": "conflicting",
    "BLOCKED": "blocked",
    "OUT_OF_SCOPE": "out_of_scope",
    "SUPERSEDED": "superseded",
    "DEFERRED": "deferred",
}


def compute_gates(
    run: Run, backlog: dict[str, Any], review: dict[str, Any], checks: dict[str, Any]
) -> dict[str, Any]:
    request = run.request()
    levels = set(request["levels"])
    det = run.evidence("deterministic_check", CHECKS, "checks", "runtime deterministic checks")
    rev = run.evidence("review", REVIEW, "independent_review", "independent source-first review")
    keys = backlog.get("keys", {})
    items = {keys.get(i["id"], i["id"]): i for i in backlog["items"]}
    stories = [k for k, i in items.items() if i["type"] == "story"]
    rev_items = {e["key"]: e for e in review.get("items", [])}
    rev_crits = {e["key"]: e for e in review.get("criteria", [])}
    obligations = review.get("independent_obligations", [])
    separate = review["reviewer"]["independence"] == "separate_agent"
    results: dict[str, dict[str, Any]] = {}

    def put(
        gid: str,
        status: str,
        reason: str,
        evidence: list[dict[str, Any]] | None = None,
        denominator: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "id": gid,
            "status": status,
            "scope": next(g.name for g in GATES if g.id == gid),
            "validator_version": __version__,
            "reason": reason,
            "evidence": evidence or [],
        }
        if denominator:
            entry["denominator"] = denominator
        results[gid] = entry

    # G01 source integrity
    g01 = checks["G01"]
    den01 = {
        "examined": g01["members_read"],
        "total": g01["members_total"],
        "provenance": "independent_inventory",
        "inventory_ref": INVENTORY,
        "inventory_digest": run.artifact_digest(INVENTORY),
        "reading_complete": g01["reading_complete"],
        "breakdown": {
            "covered": g01["members_read"],
            "partially_covered": g01["members_partial"],
            "blocked": g01["members_total"] - g01["members_read"] - g01["members_partial"],
        },
    }
    if g01["reading_complete"]:
        how = ", ".join(f"{k}: {v}" for k, v in g01.get("reading_methods", {}).items())
        put(
            "G01",
            "PASS",
            "every inventoried member was read and re-read by the reviewer"
            + (f" (reading methods: {how})" if how else ""),
            [det, rev],
            den01,
        )
    else:
        put("G01", "BLOCKED", "incomplete reading: " + "; ".join(g01["unread"]), [det, rev], den01)

    # G02 requirements coverage (independent reviewer inventory)
    counts = Counter(_BREAKDOWN[o["disposition"]] for o in obligations)
    den02 = {
        "examined": len(obligations),
        "total": len(obligations),
        "provenance": "independent_inventory",
        "inventory_ref": REVIEW,
        "inventory_digest": run.artifact_digest(REVIEW),
        "reading_complete": g01["reading_complete"],
        "breakdown": dict(sorted(counts.items())),
    }
    if counts["not_covered"] or counts["partially_covered"]:
        put("G02", "FAIL", f"coverage gaps in independent inventory: {dict(counts)}", [det, rev], den02)
    elif counts["blocked"] or not g01["reading_complete"]:
        put(
            "G02",
            "BLOCKED",
            "coverage cannot be certified: incomplete reading or blocked obligations",
            [det, rev],
            den02,
        )
    else:
        put(
            "G02",
            "PASS",
            f"{len(obligations)} independent obligations dispositioned without gaps",
            [det, rev],
            den02,
        )

    # G03 hierarchy
    put(
        "G03",
        "PASS" if not checks["G03"] else "FAIL",
        "hierarchy invariants hold" if not checks["G03"] else "; ".join(checks["G03"][:5]),
        [det],
    )

    # G04 traceability (deterministic reciprocity + reviewer reverse trace)
    unsupported = [k for k, e in {**rev_items, **rev_crits}.items() if e["source_support"] == "unsupported"]
    if checks["G04"] or unsupported:
        put(
            "G04",
            "FAIL",
            "; ".join([*checks["G04"][:5], f"unsupported by sources: {unsupported}"]),
            [det, rev],
        )
    else:
        put("G04", "PASS", "every item and criterion traces to claims or a justified proposal", [det, rev])

    # G05 / G06 / G07 semantic quality
    if "stories" in levels and stories:
        failed = [k for k in stories if rev_items.get(k, {}).get("verdict") == "fail"]
        put(
            "G05",
            "FAIL" if failed else "PASS",
            f"stories failing review: {failed}" if failed else f"{len(stories)} stories reviewed with INVEST",
            [rev],
        )
    else:
        put("G05", "NOT_APPLICABLE", "no stories in the requested levels")
    if "acceptance" in levels:
        failed = [k for k, e in rev_crits.items() if e["verdict"] == "fail"]
        missing = checks["G06_stories_without_criteria"]
        if failed or missing:
            put(
                "G06",
                "FAIL",
                f"criteria failing review: {failed}; functional stories without criteria: {missing}",
                [det, rev],
            )
        else:
            put("G06", "PASS", f"{len(rev_crits)} criteria reviewed individually", [det, rev])
    else:
        put("G06", "NOT_APPLICABLE", "acceptance criteria not requested")
    if "tasks" in levels and stories:
        insufficient = [k for k in stories if rev_items.get(k, {}).get("task_sufficiency") == "insufficient"]
        unknown = [
            k
            for k in stories
            if rev_items.get(k, {}).get("task_sufficiency")
            not in ("sufficient", "insufficient", "not_applicable")
        ]
        if insufficient:
            put("G07", "FAIL", f"stories with insufficient tasks: {insufficient}", [rev])
        elif unknown:
            put("G07", "NOT_RUN", f"task sufficiency not reviewed for {unknown}")
        else:
            put("G07", "PASS", "task sufficiency reviewed per story", [rev])
    else:
        put("G07", "NOT_APPLICABLE", "tasks not requested")

    # G08 dependencies
    if "dependencies" in levels:
        if checks["G08"]:
            put("G08", "FAIL", "; ".join(checks["G08"]), [det])
        elif review.get("dependencies_reviewed") is True:
            put("G08", "PASS", f"{len(backlog['relations'])} relations valid and reviewed", [det, rev])
        else:
            put("G08", "NOT_RUN", "relations not confirmed by the reviewer")
    else:
        put("G08", "NOT_APPLICABLE", "dependencies not requested")

    # G09 scope
    scope_issues = [
        f["affects"]
        for f in review.get("findings", [])
        if f["classification"] == "unsupported_assumption"
        and f.get("review_status", "confirmed") == "confirmed"
    ]
    if unsupported or scope_issues:
        put("G09", "FAIL", f"unsupported scope: {unsupported + [a for s in scope_issues for a in s]}", [rev])
    else:
        put("G09", "PASS", "no unsupported scope; exclusions and conflicts recorded", [rev])

    put(
        "G10",
        "NOT_APPLICABLE",
        "no sprint planning requested; generated fields contain no assignments, dates or "
        "completed work (enforced at design submission)",
    )
    put(
        "G11",
        "PASS" if not checks["G11"] else "FAIL",
        "exports deterministic and consistent across formats"
        if not checks["G11"]
        else "; ".join(checks["G11"]),
        [det],
    )
    put(
        "G12",
        "NOT_APPLICABLE",
        "no publication requested; a local package is not an authorization to publish",
    )
    total = len(rev_items) + len(rev_crits)
    if not separate:
        put(
            "G13",
            "BLOCKED",
            "review ran as a sequential role of the same agent (reduced independence)",
            [rev],
        )
    elif total != len(items) + len(backlog["criteria"]) or not obligations:
        put("G13", "FAIL", "review does not cover every item and criterion", [rev])
    elif checks["G13"]:
        put("G13", "FAIL", "; ".join(checks["G13"]), [det, rev])
    else:
        put(
            "G13",
            "PASS",
            f"reviewer distinct from every reader, orchestrator and designer; own verified-quote inventory "
            f"({len(obligations)} obligations) cites every source that yielded obligations; judged {total} "
            "items/criteria. Agent identities are self-reported by the host.",
            [det, rev],
        )
    dups = [d for d in review.get("duplicates", []) if d["assessment"] == "duplicate"]
    put(
        "G14",
        "FAIL" if dups else "PASS",
        f"confirmed duplicates: {[d.get('items') for d in dups]}"
        if dups
        else "duplicate candidates assessed",
        [rev],
    )
    change_findings = [
        f
        for f in review.get("findings") or []
        if f.get("gate") == "G15" and f.get("review_status", "confirmed") == "confirmed"
    ]
    imported = any(i.get("origin") == "imported" and not i.get("claim_refs") for i in backlog["items"])
    if backlog.get("decisions") or change_findings:
        problems = checks["G15"] + [
            f"reviewer: {f['actual']} (expected: {f['expected']})" for f in change_findings
        ]
        reason = "superseded claims not used by active work"
        if imported and not problems:
            # imported work carries no claim trace: only the reviewer's reading can see supersession
            reason += "; imported work is assessed by the independent reviewer only (no claim trace)"
        put(
            "G15",
            "PASS" if not problems else "FAIL",
            reason if not problems else "; ".join(problems),
            [det, rev],
        )
    else:
        put("G15", "NOT_APPLICABLE", "no decisions or prior versions in this run")
    put(
        "G16",
        "PASS" if not checks["G16"] else "FAIL",
        "outputs privacy-clean; run made zero remote calls"
        if not checks["G16"]
        else "; ".join(checks["G16"]),
        [det],
    )
    if "azure" in request["formats"]:
        put(
            "G17",
            "BLOCKED",
            "target compatibility needs a discovered or mock target schema; only unverified "
            f"default profile {request['profile']} was used"
            + (f" ({'; '.join(checks['G17'])})" if checks["G17"] else ""),
        )
    else:
        put("G17", "NOT_APPLICABLE", "no target package requested")
    put(
        "G18",
        "NOT_RUN",
        "no live round-trip: nothing was published from this run; a mock round-trip "
        "(pbd azure apply/verify) never counts as live; live qualification requires separate authorization",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "pbd.gate-report",
        "run_id": run.run_id,
        "gates": [results[g.id] for g in GATES],
    }
