"""Versioned handoff to Functional Test Designer (FTD).

PBD is not an authority for FTD. The handoff gives FTD what it needs to do its own work:
the ORIGINAL sources with roles and digests (FTD re-reads them independently), PBD's reconciled
requirements with locators and quotes, decisions, open questions, and the backlog's work items and
acceptance criteria as navigable context. It also drafts an FTD normalized request: sources with
FTD roles, guidance, criteria as *seeds* (ideas to consider, never coverage claims) and open
questions as ambiguities. Tracker links are included only when verified. PBD never writes Test
Cases.
"""

from __future__ import annotations

from typing import Any

from pbd import __version__
from pbd.core.canonical import digest

HANDOFF_VERSION = "1.0"
FTD_ROLE = {
    "functional": "FUNCTIONAL_AUTHORITY",
    "decision": "FUNCTIONAL_AUTHORITY",
    "implementation_evidence": "IMPLEMENTATION_EVIDENCE",
    "technical": "TECHNICAL_CONTEXT",
    "existing_backlog": "TECHNICAL_CONTEXT",
    "corroboration": "TECHNICAL_CONTEXT",
    "instructions": "TECHNICAL_CONTEXT",
    "other": "TECHNICAL_CONTEXT",
}
ACTIVE_CRITERIA = {"confirmed", "proposed"}


def _active(node: dict[str, Any]) -> bool:
    return (node.get("temporal") or {}).get("status") not in ("superseded", "withdrawn")


def build_handoff(backlog: dict[str, Any], keys: dict[str, str] | None = None) -> dict[str, Any]:
    keys = keys or {}
    crits_by: dict[str, list[dict[str, Any]]] = {}
    for c in backlog["criteria"]:
        crits_by.setdefault(c["parent"], []).append(c)
    items = []
    seeds = []
    for item in backlog["items"]:
        crits = sorted(crits_by.get(item["id"], []), key=lambda c: c.get("order", 0))
        acceptance = [
            {
                "id": c["id"],
                "key": keys.get(c["id"]),
                "visible_id": c.get("visible_id"),
                "text": c.get("text"),
                "condition": c.get("condition"),
                "trigger": c.get("trigger"),
                "expected_outcomes": c["expected_outcomes"],
                "status": c["status"],
                "claim_refs": c["claim_refs"],
            }
            for c in crits
        ]
        items.append(
            {
                "id": item["id"],
                "key": keys.get(item["id"]),
                "type": item["type"],
                "title": item["title"],
                "parent": item["parent"],
                "status": item["status"],
                "active": _active(item),
                "claim_refs": item["claim_refs"],
                "tracker_links": [r for r in item.get("external_refs", []) if r.get("verified") is True],
                "acceptance": acceptance,
            }
        )
        if _active(item):
            for c in crits:
                if c["status"] in ACTIVE_CRITERIA:
                    parts = [c.get("condition"), c.get("trigger"), *c["expected_outcomes"]]
                    text = c.get("text") or " — ".join(p for p in parts if p)
                    seeds.append(
                        {"text": f"[{c.get('visible_id', '')}] {text}".strip(), "section": item["title"]}
                    )
    open_q = [q for q in backlog["questions"] if q["status"] == "open"]
    sources = [
        {
            "selector": s["selector"],
            "authority": s["authority"],
            "ftd_role": FTD_ROLE.get(s["authority"], "TECHNICAL_CONTEXT"),
            "digest": s["digest"],
            "read_status": s.get("read_status"),
            "members": [
                {"path": m["path"], "digest": m.get("digest"), "status": m["status"]}
                for m in s.get("members", [])
            ],
        }
        for s in backlog["sources"]
    ]
    doc: dict[str, Any] = {
        "kind": "pbd.ftd-handoff",
        "handoff_version": HANDOFF_VERSION,
        "pbd_version": __version__,
        "backlog_digest": digest({k: v for k, v in backlog.items() if k not in ("keys", "_digest")}),
        "run_id": backlog["run_id"],
        "language": backlog["language"],
        "synthetic": bool(backlog.get("synthetic")),
        "authority_note": (
            "PBD is not an authority for test design. Read the original sources below independently; "
            "use requirements, criteria and questions only as context and seeds."
        ),
        "sources": sources,
        "requirements": [
            {
                "id": c["id"],
                "key": keys.get(c["id"]),
                "text": c["text"],
                "category": c["category"],
                "disposition": c["disposition"]["status"],
                "superseded": (c.get("temporal") or {}).get("status") == "superseded",
                "evidence": [
                    {"locator": ev.get("locator"), "quote": ev.get("summary")}
                    for ev in c["evidence"]
                    if ev.get("type") == "source_locator"
                ],
            }
            for c in backlog["claims"]
        ],
        "decisions": [
            {
                "id": d["id"],
                "text": d["text"],
                "status": d["status"],
                "supersedes": d.get("supersedes_claims", []),
            }
            for d in backlog.get("decisions", [])
        ],
        "open_questions": [
            {
                "id": q["id"],
                "text": q["text"],
                "impact": q["impact"],
                "blocking": q["blocking"],
                "affects": q["affects"],
            }
            for q in open_q
        ],
        "work_items": items,
        "ftd_request_draft": {
            "sources": [
                {
                    "path": s["selector"],
                    "role": s["ftd_role"],
                    "purpose": f"{s['authority']} source selected for PBD",
                }
                for s in sources
            ],
            "guidance": [
                "Derive test cases from the functional authority; "
                "PBD criteria are seeds, not coverage evidence.",
                f"Write test cases in {backlog['language']}.",
            ],
            "seeds": seeds,
            "ambiguities": [q["text"] for q in open_q],
        },
        "test_cases": [],
        "note": "PBD does not create Test Cases; FTD owns them.",
    }
    return doc
