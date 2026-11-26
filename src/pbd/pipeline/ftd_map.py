"""PBD → FTD traceability sidecar (QL-021): which FTD Test Cases a PBD seed led to.

Deterministic and exact. The handoff (1.1+) puts each criterion's canonical PBD ID at the start of
its seed text (``[PBD-AC-…] …``); FTD keeps each seed's text verbatim in its
``guidance_dispositions`` with the Test Case IDs it materialized or found already covering it.
This module joins the two by the canonical ID token only — never by title, wording or seed order.
A seed whose text carries no known PBD ID stays *unresolved* (for example historical handoffs that
only carried the per-story visible ID ``CA-01``, which repeats in every story).

The map is planning traceability, not coverage evidence: FTD's original sources stay the authority,
a linked seed does not mean the criterion is covered, and a designed Test Case is not an executed
one. Many-to-many links, blocked cases and unresolved seeds are all kept.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pbd.core.canonical import digest

MAP_VERSION = "1.0"
PBD_ID = re.compile(r"\bPBD-(?:AC|EPIC|FEAT|STORY|ENAB|SPIKE|BUG|TASK)-[0-9A-HJKMNP-TV-Z]{12}\b")
EXECUTED = frozenset(
    {"PASSED", "FAILED", "EXECUTED", "EXECUTED_PASS", "EXECUTED_FAIL", "BLOCKED_IN_EXECUTION"}
)


def _known_ids(handoff: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in handoff.get("work_items") or []:
        out[item["id"]] = {"kind": "item", "item": item["id"], "title": item.get("title")}
        for c in item.get("acceptance") or []:
            out[c["id"]] = {"kind": "criterion", "item": item["id"], "visible_id": c.get("visible_id")}
    return out


def build_map(
    handoff: dict[str, Any], ftd: dict[str, Any], backlog: dict[str, Any] | None = None
) -> dict[str, Any]:
    if handoff.get("kind") != "pbd.ftd-handoff":
        raise ValueError("not a PBD FTD handoff (kind pbd.ftd-handoff)")
    if not isinstance(ftd.get("test_cases"), list) or not isinstance(ftd.get("guidance_dispositions"), list):
        raise ValueError("not an FTD test-cases.json (test_cases and guidance_dispositions required)")
    known = _known_ids(handoff)
    cases = {tc["id"]: tc for tc in ftd["test_cases"] if isinstance(tc, dict) and tc.get("id")}
    seen: Counter[str] = Counter()
    links: list[dict[str, Any]] = []
    for disp in ftd["guidance_dispositions"]:
        anchor = str(disp.get("item", ""))
        if "#seed-" not in anchor:
            continue  # guidance items are method notes, not seeds
        seen[anchor] += 1
        tokens = list(dict.fromkeys(PBD_ID.findall(str(disp.get("text", "")))))
        found = [t for t in tokens if t in known]
        refs = [str(r) for r in disp.get("test_refs") or []]
        status = "linked" if found else "dangling" if tokens else "unresolved"
        links.append(
            {
                "seed": anchor,
                "status": status,
                "pbd_ids": found,
                "unknown_pbd_ids": [t for t in tokens if t not in known],
                "pbd_items": sorted({known[t]["item"] for t in found}),
                "disposition": disp.get("disposition"),
                "question_ref": disp.get("question_ref"),
                "test_cases": [r for r in refs if r in cases],
                "missing_test_cases": [r for r in refs if r not in cases],
            }
        )
    duplicates = sorted(a for a, n in seen.items() if n > 1)
    by_pbd: dict[str, set[str]] = {}
    for link in links:
        for pid in link["pbd_ids"]:
            by_pbd.setdefault(pid, set()).update(link["test_cases"])
    linked_cases = {tc for link in links if link["status"] == "linked" for tc in link["test_cases"]}
    executed = [tid for tid, tc in cases.items() if str(tc.get("execution_status")) in EXECUTED]
    stale = None
    if backlog is not None:
        current = digest({k: v for k, v in backlog.items() if k not in ("keys", "_digest")})
        stale = current != handoff.get("backlog_digest")
    status_counts = Counter(link["status"] for link in links)
    return {
        "kind": "pbd.ftd-map",
        "map_version": MAP_VERSION,
        "handoff_version": handoff.get("handoff_version"),
        "handoff_digest": digest(handoff),
        "ftd_test_cases_digest": digest(ftd),
        "ftd_schema_version": ftd.get("schema_version"),
        "backlog_digest": handoff.get("backlog_digest"),
        "run_id": handoff.get("run_id"),
        "stale_against_backlog": stale,
        "authority_note": "The original sources are FTD's authority; PBD seeds are planning guidance. "
        "A link is traceability, not coverage evidence.",
        "links": links,
        "by_pbd_id": {pid: sorted(tcs) for pid, tcs in sorted(by_pbd.items())},
        "duplicate_seed_anchors": duplicates,
        "counts": {
            "seeds": len(links),
            "linked": status_counts["linked"],
            "unresolved": status_counts["unresolved"],
            "dangling": status_counts["dangling"],
            "pbd_ids_linked": len(by_pbd),
            "test_cases_total": len(cases),
            "test_cases_linked": len(linked_cases),
            "test_cases_unlinked": len(cases) - len(linked_cases),
            "designed": len(cases),
            "executed": len(executed),
            "blocked": sum(1 for tc in cases.values() if str(tc.get("status", "")).startswith("BLOCKED")),
        },
    }


def instructions_markdown(handoff: dict[str, Any]) -> str:
    """FTD instructions draft from a handoff: sources with roles, guidance, seeds keeping the canonical
    PBD ID at the start of each seed, and open questions as ambiguities (FTD treats all of it as
    guidance, never authority)."""
    req = handoff["ftd_request_draft"]
    lines = ["# Instructions for Functional Test Designer (from a PBD handoff)", ""]
    lines += ["## Sources", ""] + [f"- `{s['path']}` — {s['role']}" for s in req["sources"]]
    lines += ["", "## Guidance", ""] + [f"- {g}" for g in req["guidance"]]
    lines += [
        "- Keep the `[PBD-…]` identifier at the start of each seed exactly as written: it is how PBD links "
        "your Test Cases back to its backlog.",
        "",
        "## Seeds (ideas to consider, not coverage claims)",
        "",
    ]
    section = None
    for seed in req["seeds"]:
        if seed.get("section") != section:
            section = seed.get("section")
            lines += ["", f"### {section}", ""]
        lines.append(f"- {seed['text']}")
    if req["ambiguities"]:
        lines += ["", "## Open questions (ambiguities)", ""] + [f"- {a}" for a in req["ambiguities"]]
    return "\n".join(lines) + "\n"
