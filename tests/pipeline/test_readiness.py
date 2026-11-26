"""Readiness contract (schema 1.2.0, QL-019): open blocking questions, typed blocker links, propagation.

The agent judges whether missing information prevents work; these tests only exercise what the
runtime enforces: references resolve, declared statuses do not contradict each other or the
confirmed dependency graph, blocked work never enters a sprint, and the reviewer's readiness check
drives G08. Two unrelated synthetic domains are used (community garden, library loans).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.design import compile_design, submit_claims, submit_design
from pbd.pipeline.finalize import finalize
from pbd.pipeline.planning import plan
from pbd.pipeline.review import submit_review, validate_review
from pbd.pipeline.run import Run, normalize_request, start
from pbd.validation.invariants import check_readiness
from tests.pipeline.helpers import claims_payload, design_payload, make_workspace, read_all
from tests.pipeline.test_review_finalize import review_payload


@pytest.fixture
def read_run(tmp_path: Path) -> Run:
    ws = make_workspace(tmp_path)
    run = start(
        tmp_path / "out",
        ws,
        [("prd.md", "functional"), ("decisoes", "decision")],
        normalize_request(synthetic=True),
    )
    read_all(run)
    submit_claims(run, claims_payload(run))
    return run


def _items(p: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {i["key"]: i for i in p["items"]}


def _blocking(p: dict[str, Any], affects: list[str]) -> dict[str, Any]:
    q = p["questions"][0]
    q.update(blocking=True, affects=affects)
    return q


def _errors(run: Run, p: dict[str, Any]) -> list[str]:
    errors, _ = compile_design(run, p)
    return errors


def test_buildable_work_must_declare_readiness(read_run: Run) -> None:
    p = design_payload()
    del _items(p)["T1"]["readiness"]
    assert any("T1: readiness is required" in e for e in _errors(read_run, p))
    p = design_payload()
    _items(p)["T1"]["readiness"] = {"status": "ready_to_build", "rationale": "x"}
    assert any("readiness.status must be one of" in e for e in _errors(read_run, p))
    p = design_payload()
    _items(p)["T1"]["readiness"] = {"status": "blocked", "rationale": "sem resposta"}
    assert any("must cite what blocks it" in e for e in _errors(read_run, p))


def test_open_blocking_question_blocks_dependent_work(read_run: Run) -> None:
    p = design_payload()
    _blocking(p, ["US1", "T1"])
    items = _items(p)
    # the c08 defect: the question is raised but the dependent task is still ready to build
    errors = _errors(read_run, p)
    assert any("blocking question blocks no work" in e for e in errors)
    assert any("neither is blocked by it nor states why" in e for e in errors)
    items["T1"]["readiness"] = {
        "status": "ready",
        "rationale": "pronta",
        "blocked_by": [{"ref": "Q1", "rationale": "duração define o limite"}],
    }
    assert any("declared ready but blocked by an open blocking question" in e for e in _errors(read_run, p))
    items["T1"]["readiness"]["status"] = "blocked"
    errors = _errors(read_run, p)
    # the parent story is still declared ready while its task is blocked: must be partial
    assert any("declared ready but children are blocked" in e for e in errors)
    assert any("affects" in e and "neither" in e for e in errors)  # US1 lacks a disposition too
    items["US1"]["readiness"] = {
        "status": "partial",
        "rationale": "a verificação de disponibilidade espera a duração da temporada",
        "independent_of": [{"ref": "Q1", "rationale": "o registro da reserva não depende da duração"}],
    }
    errors, backlog = compile_design(read_run, p)
    assert errors == []
    by_key = {k: v for v, k in backlog["keys"].items()}
    t1 = next(i for i in backlog["items"] if i["id"] == by_key["T1"])
    q1 = backlog["questions"][0]
    assert t1["readiness"]["blocked_by"] == [{"ref": q1["id"], "rationale": "duração define o limite"}]
    # an unrelated sibling keeps its own readiness: no blocking by association
    us2 = next(i for i in backlog["items"] if i["id"] == by_key["US2"])
    assert us2["readiness"]["status"] == "ready"


def test_nonblocking_question_cannot_block_and_refs_must_resolve(read_run: Run) -> None:
    p = design_payload()
    _items(p)["T1"]["readiness"] = {
        "status": "blocked",
        "rationale": "x",
        "blocked_by": [{"ref": "Q1", "rationale": "y"}],
    }
    _items(p)["US1"]["readiness"]["status"] = "partial"
    assert any("blocked by non-blocking question" in e for e in _errors(read_run, p))
    _items(p)["T1"]["readiness"]["blocked_by"] = [{"ref": "NOPE", "rationale": "y"}]
    assert any("must cite a question or item key" in e for e in _errors(read_run, p))
    _items(p)["T1"]["readiness"]["blocked_by"] = [{"ref": "Q1"}]
    assert any("needs a rationale" in e for e in _errors(read_run, p))


def test_blocker_propagates_through_confirmed_dependencies_only(read_run: Run) -> None:
    p = design_payload()
    p["questions"][0].update(blocking=True, affects=["US2"])
    _items(p)["US2"]["readiness"] = {
        "status": "blocked",
        "rationale": "consulta depende da regra da temporada",
        "blocked_by": [{"ref": "Q1", "rationale": "duração"}],
    }
    p["relations"] = [
        {"source": "US2", "target": "US1", "type": "predecessor", "status": "proposed", "reason": "ordem"}
    ]
    assert _errors(read_run, p) == []  # a proposed edge does not propagate a blocker
    p["relations"][0]["status"] = "confirmed"
    assert any("waits for blocked predecessor" in e for e in _errors(read_run, p))


def _library_backlog() -> dict[str, Any]:
    """Second synthetic domain (library loans), checked at the invariant level."""
    q = {
        "id": "PBD-Q-000000000001",
        "text": "Which card reader model will the kiosk use?",
        "impact": "Driver work cannot start.",
        "blocking": True,
        "affects": ["PBD-TASK-000000000002", "PBD-SPIKE-00000000000S"],
        "status": "open",
    }
    item = lambda iid, itype, parent, rd: {  # noqa: E731
        "id": iid,
        "type": itype,
        "title": iid,
        "parent": parent,
        "claim_refs": [],
        "technical_rationale": "fixture",
        "origin": "generated",
        "status": "draft",
        "readiness": rd,
    }
    story = "PBD-STORY-000000000001"
    return {
        "items": [
            item(story, "story", None, {"status": "partial", "rationale": "driver waits"}),
            item(
                "PBD-TASK-000000000002",
                "task",
                story,
                {
                    "status": "blocked",
                    "rationale": "x",
                    "blocked_by": [{"ref": q["id"], "rationale": "model"}],
                },
            ),
            item(
                "PBD-TASK-000000000003", "task", story, {"status": "ready", "rationale": "loan rules known"}
            ),
            item(
                "PBD-SPIKE-00000000000S",
                "spike",
                story,
                {
                    "status": "ready",
                    "rationale": "bounded comparison of two candidate readers",
                    "independent_of": [{"ref": q["id"], "rationale": "the spike informs the answer"}],
                },
            ),
        ],
        "questions": [q],
        "relations": [],
        "decisions": [],
    }


def test_second_domain_valid_investigation_and_stale_decision() -> None:
    doc = _library_backlog()
    assert check_readiness(doc) == []
    # closing the question without recomputing readiness leaves a stale blocker
    doc["questions"][0].update(status="answered", answer_decision="PBD-DEC-000000000001")
    issues = check_readiness(doc)
    assert any("which is answered: recompute readiness" in i.message for i in issues)
    # the story cannot claim ready while a child is still blocked
    doc = _library_backlog()
    doc["items"][0]["readiness"]["status"] = "ready"
    assert any("use partial" in i.message for i in check_readiness(doc))
    # artifacts before 1.2.0 carry no readiness and are not checked (unassessed)
    legacy = _library_backlog()
    for i in legacy["items"]:
        del i["readiness"]
    assert check_readiness(legacy) == []


def test_planning_never_schedules_blocked_work() -> None:
    doc = _library_backlog()
    sp = {"state": "confirmed", "value": 2, "evidence": [{"type": "user_statement"}]}
    for item in doc["items"][1:]:
        item["fields"] = {"story_points": sp}
    doc["criteria"] = []
    doc["relations"] = [
        {
            "id": "PBD-REL-000000000001",
            "type": "predecessor",
            "source": "PBD-TASK-000000000002",
            "target": "PBD-TASK-000000000003",
            "status": "proposed",
            "reason": "driver before loan screen",
        }
    ]
    result = plan(doc, {"capacity": {"unit": "story_points", "per_sprint": 10}})
    planned = {i for s in result["sprints"] for i in s["items"]}
    assert "PBD-TASK-000000000002" not in planned
    reasons = {u["item"]: u["reason"] for u in result["unplanned"]}
    assert reasons["PBD-TASK-000000000002"].startswith("blocked by ['PBD-Q-000000000001']")
    # its successor waits instead of being forced into a sprint
    assert "waits for unplanned predecessors" in reasons["PBD-TASK-000000000003"]
    assert "PBD-SPIKE-00000000000S" in planned
    assert result["checks"]["not_ready"][0]["item"] == "PBD-TASK-000000000002"
    seq = {s["item"]: s["readiness"] for s in result["sequence"]}
    assert seq["PBD-TASK-000000000002"] == "blocked"


def _finalized(tmp_path: Path, mutate: Any = None) -> dict[str, Any]:
    ws = make_workspace(tmp_path)
    run = start(
        tmp_path / "out",
        ws,
        [("prd.md", "functional"), ("decisoes", "decision")],
        normalize_request(synthetic=True),
    )
    read_all(run)
    submit_claims(run, claims_payload(run))
    p = design_payload()
    submit_design(run, p)
    review = review_payload(run)
    if mutate:
        mutate(review)
    assert validate_review(run, review) == []
    submit_review(run, review)
    finalize(run)
    return {g["id"]: g for g in run.read("output/gates.json")["gates"]}


def test_g08_reflects_reviewer_readiness_judgment(tmp_path: Path) -> None:
    gates = _finalized(tmp_path / "a")
    assert gates["G08"]["status"] == "PASS"
    assert "readiness ready: 3 (agreed by the reviewer)" in gates["G08"]["reason"]

    def dispute(r: dict[str, Any]) -> None:
        t1 = next(e for e in r["items"] if e["key"] == "T1")
        t1.update(readiness_check="dispute", readiness_notes="depends on an unanswered season rule")

    gates = _finalized(tmp_path / "b", dispute)
    assert gates["G08"]["status"] == "FAIL"
    assert "reviewer disputes readiness of ['T1']" in gates["G08"]["reason"]


def test_reviewer_must_check_declared_readiness(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path)
    run = start(
        tmp_path / "out",
        ws,
        [("prd.md", "functional"), ("decisoes", "decision")],
        normalize_request(synthetic=True),
    )
    read_all(run)
    submit_claims(run, claims_payload(run))
    submit_design(run, design_payload())
    review = review_payload(run)
    for e in review["items"]:
        e.pop("readiness_check", None)
    assert any("readiness_check must be agree or dispute" in e for e in validate_review(run, review))
    review = review_payload(run)
    review["items"][-1]["readiness_check"] = "dispute"
    assert any("readiness dispute needs readiness_notes" in e for e in validate_review(run, review))
