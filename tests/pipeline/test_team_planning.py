"""Team planning (CP3): owners vs assignees, per-person capacity, units, blockers, order.

Synthetic scenario (not a default policy): two developers and two five-day sprints, frontend,
backend, integration and QA tasks, a story with mixed child assignees, an unassigned task, a
blocked story, a preparation task placed before its story's sprint and, in a variant, insufficient
capacity. Placement and owners stand in for an agent's proposal; the runtime only checks them.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from pbd.pipeline.planning import PlanningError, is_stale, plan

USER = [{"type": "user_statement", "summary": "estimate given by the team"}]


def _item(iid: str, itype: str, parent: str | None, **fields: Any) -> dict[str, Any]:
    return {
        "id": iid,
        "type": itype,
        "title": iid,
        "parent": parent,
        "claim_refs": [],
        "origin": "generated",
        "status": "reviewed",
        "fields": {k: {"state": "confirmed", "value": v, "evidence": USER} for k, v in fields.items()},
        "readiness": {"status": "ready", "rationale": "fixture"},
    }


S1, S2, S3 = "PBD-STORY-000000000001", "PBD-STORY-000000000002", "PBD-STORY-000000000003"
T = {n: f"PBD-TASK-00000000000{n}" for n in range(1, 9)}
Q = "PBD-Q-000000000001"


def _backlog() -> dict[str, Any]:
    items = [
        _item("PBD-FEAT-000000000001", "feature", None),
        _item(S1, "story", "PBD-FEAT-000000000001", story_points=3),
        _item(T[1], "task", S1, original_estimate=4),  # frontend
        _item(T[2], "task", S1, original_estimate=6),  # backend
        _item(T[3], "task", S1, original_estimate=3),  # QA
        _item(S2, "story", "PBD-FEAT-000000000001", story_points=5),
        _item(T[4], "task", S2, original_estimate=2),  # shared API contract (preparation)
        _item(T[5], "task", S2, original_estimate=8),  # backend
        _item(T[6], "task", S2, original_estimate=5),  # frontend
        _item(T[7], "task", S2, original_estimate=4),  # integration, unassigned
        _item(S3, "story", "PBD-FEAT-000000000001", story_points=8),
        _item(T[8], "task", S3, original_estimate=6),
    ]
    blocked = {
        "status": "blocked",
        "rationale": "partner contract unknown",
        "blocked_by": [{"ref": Q, "rationale": "x"}],
    }
    items[10]["readiness"] = blocked
    items[11]["readiness"] = blocked
    del items[0]["readiness"]
    return {
        "run_id": "PBD-RUN-000000000000",
        "items": items,
        "criteria": [],
        "questions": [
            {
                "id": Q,
                "text": "Which partner?",
                "impact": "x",
                "blocking": True,
                "affects": [S3],
                "status": "open",
            }
        ],
        "relations": [
            {
                "id": "PBD-REL-000000000001",
                "type": "predecessor",
                "source": S1,
                "target": S2,
                "status": "confirmed",
                "reason": "payment needs registration",
            },
        ],
    }


def _input() -> dict[str, Any]:
    return {
        "team": [
            {"id": "dev-a", "skills": ["backend"], "capacity": {"unit": "hours", "per_sprint": 30}},
            {
                "id": "dev-b",
                "skills": ["frontend", "qa"],
                "capacity": {"unit": "hours", "per_sprint": {"1": 30, "2": 20}},
            },
        ],
        "sprints": [
            {"index": 1, "working_days": 5, "goal": "Cadastro"},
            {"index": 2, "working_days": 5, "goal": "Pagamento"},
        ],
        "responsibility": "story_owner",
        "proposal": {
            "placement": {S1: 1, S2: 2, T[4]: 1},
            "owners": {S1: "dev-a", S2: "dev-b"},
            "assignees": {
                T[1]: "dev-b",
                T[2]: "dev-a",
                T[3]: "dev-b",
                T[4]: "dev-a",
                T[5]: "dev-b",
                T[6]: "dev-a",
            },
            "rationale": {S2: "Contract first so frontend and backend proceed in parallel."},
        },
        "assessments": {
            S2: {
                "complexity": "high",
                "risk": "medium",
                "confidence": "medium",
                "rationale": "payment states",
            }
        },
    }


def _people(doc: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    return {(p["member"], p["sprint"]): p for p in doc["team_plan"]["people"]}


def test_two_developers_two_sprints_exact_loads_and_roles() -> None:
    doc = plan(_backlog(), _input())
    tp = doc["team_plan"]
    assert tp["g10"]["status"] == "PASS", tp["g10"]
    people = _people(doc)
    assert (
        people[("dev-a", 1)]["load"] == 8 and people[("dev-a", 1)]["remaining"] == 22
    )  # T2 + preparation T4
    assert people[("dev-b", 1)]["load"] == 7  # T1 + T3 (frontend and QA of a story owned by dev-a)
    assert people[("dev-a", 2)]["load"] == 5 and people[("dev-b", 2)]["load"] == 8
    assert people[("dev-b", 2)]["remaining"] == 12  # availability 20 in sprint 2
    rows = {r["story"]: r for r in tp["stories"]}
    assert rows[S1]["owner"] == "dev-a" and rows[S1]["owner_provenance"] == "proposed"
    s1_tasks = {t["task"]: t for t in rows[S1]["tasks"]}
    assert s1_tasks[T[1]]["assignee"] == "dev-b" and s1_tasks[T[1]]["collaborator"] is True
    prep = {t["task"]: t for t in rows[S2]["tasks"]}[T[4]]
    assert prep["sprint"] == 1 and prep["timing"] == "preparation"
    # the unassigned task is listed, never counted twice nor silently given to the owner
    assert tp["unassigned_tasks"] == [T[7]]
    assert all(T[7] not in p["counted"] for p in tp["people"])
    counted = [i for p in tp["people"] for i in p["counted"]]
    assert len(counted) == len(set(counted))
    # the blocked story is unallocated with its blocker, not forced into a sprint
    assert tp["unallocated"] == [{"item": S3, "reason": tp["unallocated"][0]["reason"]}]
    assert tp["unallocated"][0]["reason"].startswith("blocked")
    assert [s["stories"] for s in tp["sprints"]] == [[S1], [S2]]
    assert tp["assessments"][S2]["complexity"] == "high"


def test_insufficient_capacity_is_exposed_not_balanced() -> None:
    inp = _input()
    inp["team"][1]["capacity"]["per_sprint"] = {"1": 30, "2": 5}
    tp = plan(_backlog(), inp)["team_plan"]
    assert tp["g10"]["status"] == "FAIL"
    assert any("dev-b: sprint 2 load 8 exceeds capacity 5 hours" in v for v in tp["violations"])


def test_blocked_work_and_dependency_order_are_violations() -> None:
    inp = _input()
    inp["proposal"]["placement"].update({S3: 2})
    inp["proposal"]["owners"][S3] = "dev-a"
    tp = plan(_backlog(), inp)["team_plan"]
    assert any(v.startswith(f"{S3}: placed in sprint 2 but blocked") for v in tp["violations"])
    inp = _input()
    inp["proposal"]["placement"].update({S1: 2, S2: 1})
    tp = plan(_backlog(), inp)["team_plan"]
    assert any("before its predecessor" in v for v in tp["violations"])


def test_one_accountable_owner_when_requested_and_delegation_is_derived() -> None:
    inp = _input()
    del inp["proposal"]["owners"][S2]
    tp = plan(_backlog(), inp)["team_plan"]
    assert any("without the accountable owner" in v for v in tp["violations"])
    inp = _input()
    inp["responsibility"] = "whole_story_delegation"
    inp["proposal"]["assignees"] = {}
    tp = plan(_backlog(), inp)["team_plan"]
    s2 = {t["task"]: t for r in tp["stories"] if r["story"] == S2 for t in r["tasks"]}
    assert {t["assignee"] for t in s2.values()} == {"dev-b"}
    assert {t["assignee_provenance"] for t in s2.values()} == {"derived_delegation"}
    assert any("never changes child assignments" in n for n in tp["notes"])


def test_actual_snapshot_stays_separate_from_the_proposal() -> None:
    inp = _input()
    inp["actual"] = {"source": "snapshot.json", "assignees": {T[5]: "dev-a", T[7]: "dev-a"}}
    tp = plan(_backlog(), inp)["team_plan"]
    s2 = {t["task"]: t for r in tp["stories"] if r["story"] == S2 for t in r["tasks"]}
    assert s2[T[5]]["assignee"] == "dev-b" and s2[T[5]]["actual_assignee"] == "dev-a"
    assert "differs from the actual" in s2[T[5]]["discrepancy"]
    assert s2[T[7]]["assignee"] == "dev-a" and s2[T[7]]["assignee_provenance"] == "actual"


def test_unknown_zero_and_unit_mismatch() -> None:
    backlog = _backlog()
    by_id = {i["id"]: i for i in backlog["items"]}
    by_id[T[6]]["fields"] = {
        "story_points": {"state": "confirmed", "value": 2, "evidence": USER}
    }  # points only
    by_id[T[2]]["fields"]["original_estimate"]["value"] = 0  # zero is a real estimate
    by_id[T[3]]["fields"] = {}  # unknown
    tp = plan(backlog, _input())["team_plan"]
    people = {(p["member"], p["sprint"]): p for p in tp["people"]}
    assert people[("dev-a", 1)]["load"] == 2 and T[2] in people[("dev-a", 1)]["counted"]
    assert people[("dev-b", 1)]["unknown_estimates"] == [T[3]] and people[("dev-b", 1)]["remaining"] is None
    assert people[("dev-a", 2)]["unit_mismatch"] == [T[6]]
    assert tp["g10"]["status"] == "BLOCKED"


def test_points_plan_counts_stories_only_and_hours_never_add_parents() -> None:
    backlog = _backlog()
    for i in backlog["items"]:
        if i["id"] == T[1]:
            i["fields"]["story_points"] = {"state": "confirmed", "value": 1, "evidence": USER}
        if i["id"] == S1:
            i["fields"]["original_estimate"] = {"state": "confirmed", "value": 40, "evidence": USER}
    pts = {
        x["item"]: x
        for x in plan(backlog, {"capacity": {"unit": "story_points", "per_sprint": 20}})["sequence"]
    }
    assert pts[T[1]]["effort"] is None and "not added" in pts[T[1]]["provenance"]["effort"]
    hrs = {x["item"]: x for x in plan(backlog, {"capacity": {"unit": "hours", "per_sprint": 40}})["sequence"]}
    assert hrs[S1]["effort"] is None and "parent hours not added" in hrs[S1]["provenance"]["effort"]


def test_input_validation_and_relative_order_only() -> None:
    bad = _input()
    bad["proposal"]["owners"][S1] = "dev-z"
    bad["proposal"]["placement"][S2] = 3
    with pytest.raises(PlanningError) as exc:
        plan(_backlog(), bad)
    assert any("unknown member 'dev-z'" in e for e in exc.value.errors)
    assert any("undeclared sprint 3" in e for e in exc.value.errors)
    # a second input with only relative order and no team data: a sequence, no people, no sprints
    doc = plan(_backlog())
    assert "team_plan" not in doc and doc["sprints"] is None
    seq = [x["item"] for x in doc["sequence"]]
    assert seq.index(S1) < seq.index(S2)
    assert {x["item"]: x["backlog_position"] for x in doc["sequence"]}[S1] < 3


def test_plan_goes_stale_when_the_backlog_changes() -> None:
    backlog = _backlog()
    doc = plan(backlog, _input())
    changed = copy.deepcopy(backlog)
    changed["items"][1]["title"] = "renamed"
    assert not is_stale(doc, backlog) and is_stale(doc, changed)


def test_plan_report_shows_owners_assignees_and_counts_from_json() -> None:
    from pbd.render.report_html import render_plan_report

    inp = _input()
    inp["actual"] = {"source": "snapshot.json", "assignees": {T[5]: "dev-a"}}
    doc = plan(_backlog(), inp)
    html = render_plan_report(doc, "Plano", "pt-BR", "test")
    tp = doc["team_plan"]
    assert "Plano do time" in html and "Rascunho local" in html
    assert html.count('data-i18n="enum.assign.derived_delegation"') == 0
    # one row per (person, sprint) and one task row per task of every story
    assert html.count("<tr><td><code>dev-") == len(tp["people"])
    assert html.count('data-i18n="enum.timing.preparation"') == 2  # sprint card + story table
    assert "proposta difere do snapshot" in html
    assert "Desconhecida" not in html  # capacity is per person, not unknown
    assert "<script>window" not in html
