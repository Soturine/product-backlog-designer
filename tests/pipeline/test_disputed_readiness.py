"""QL-020 safety gap: a reviewer readiness dispute keeps work out of build until it is resolved.

The generator's semantic judgment (is this question blocking?) is not changed here; what is tested
is that a confirmed dispute is never displayed, exported or planned as cleared work, that it can only
be cleared through an explicit resolution, and that unrelated work is not affected.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.finalize import finalize
from pbd.pipeline.planning import plan
from pbd.pipeline.refine import RefineError
from pbd.pipeline.refine import apply as refine_apply
from pbd.pipeline.refine import plan as refine_plan
from pbd.pipeline.review import submit_review
from pbd.validation.invariants import disputed_items
from tests.pipeline import test_team_planning as team
from tests.pipeline.library_fixture import designed_run, review_payload


@pytest.fixture(scope="module")
def disputed(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], Path]:
    run = designed_run(tmp_path_factory.mktemp("lib"), formats=["md", "csv"], title="Biblioteca")
    review = review_payload(run)
    t6 = next(e for e in review["items"] if e["key"] == "T6")  # mock-contract task declared ready
    t6.update(
        readiness_check="dispute", readiness_notes="o contrato simulado depende do modelo ainda indefinido"
    )
    submit_review(run, review)
    finalize(run)
    backlog = json.loads(run.path("output/backlog.json").read_text(encoding="utf-8"))
    return backlog, run.path("output")


def _id(backlog: dict[str, Any], title_start: str) -> str:
    return next(i["id"] for i in backlog["items"] if i["title"].startswith(title_start))


def test_dispute_becomes_a_confirmed_g08_finding_and_the_declaration_is_kept(disputed: Any) -> None:
    backlog, out = disputed
    t6 = _id(backlog, "Fluxo do quiosque")
    assert disputed_items(backlog) == {t6: "o contrato simulado depende do modelo ainda indefinido"}
    item = next(i for i in backlog["items"] if i["id"] == t6)
    assert item["readiness"]["status"] == "ready"  # the designer's proposal is preserved, not rewritten
    gates = {
        g["id"]: g["status"] for g in json.loads((out / "gates.json").read_text(encoding="utf-8"))["gates"]
    }
    assert gates["G08"] == "FAIL"
    html = (out / "report.html").read_text(encoding="utf-8")
    assert f'data-id="{t6}" data-type="task" data-verdict="pass" data-readiness="disputed"' in html
    assert (
        'data-readiness="disputed"' in html and html.count('data-readiness="disputed"') == 2
    )  # tree + table
    import csv
    import io

    rows = list(csv.DictReader(io.StringIO((out / "backlog.csv").read_text(encoding="utf-8-sig"))))
    row = next(r for r in rows if r["id"] == t6)
    assert row["readiness"] == "ready" and row["readiness_review"] == "disputed"
    assert {r["readiness_review"] for r in rows if r["id"] != t6} == {""}


@pytest.mark.parametrize("mode", ["story_owner", "task_split", "whole_story_delegation"])
def test_disputed_work_is_never_scheduled_in_any_responsibility_mode(mode: str) -> None:
    backlog = team._backlog()
    backlog["findings"] = [
        {"id": "PBD-FND-000000000001", "gate": "G08", "classification": "planning_gap", "severity": "medium",
         "expected": "x", "actual": "reviewer disputes", "why": "x", "impact": "x", "recommendation": "x",
         "affects": [team.T[5]], "review_status": "confirmed"}
    ]  # fmt: skip
    inp = team._input()
    inp["responsibility"] = mode
    if mode == "task_split":
        del inp["proposal"]["owners"]
    tp = plan(backlog, inp)["team_plan"]
    s2 = {t["task"]: t for r in tp["stories"] if r["story"] == team.S2 for t in r["tasks"]}
    assert s2[team.T[5]]["sprint"] is None  # disputed task stays out of the sprint
    assert any(u["item"] == team.T[5] and "disputed" in u["reason"] for u in tp["unallocated"])
    assert s2[team.T[6]]["sprint"] == 2  # unrelated sibling keeps its place
    # placing it explicitly is a violation, never silently accepted
    inp["proposal"]["placement"][team.T[5]] = 2
    tp = plan(backlog, inp)["team_plan"]
    assert any("readiness disputed by the independent review" in v for v in tp["violations"])
    # a resolved finding no longer holds it back
    backlog["findings"][0]["review_status"] = "resolved"
    assert disputed_items(backlog) == {}


def test_clearing_needs_resolution_and_reconciled_blockers(disputed: Any) -> None:
    backlog, _ = disputed
    t6 = _id(backlog, "Fluxo do quiosque")
    finding = next(f for f in backlog["findings"] if t6 in f["affects"] and f["gate"] == "G08")
    ready = {"key": "R1", "op": "set_readiness", "target": t6, "rationale": "x",
             "readiness": {"status": "ready", "rationale": "x"}}  # fmt: skip
    with pytest.raises(RefineError) as exc:
        refine_plan(backlog, {"author": {"agent": "a"}, "changes": [ready]})
    assert any("resolve_finding first" in e for e in exc.value.errors)
    resolve = {
        "key": "F1",
        "op": "resolve_finding",
        "target": finding["id"],
        "rationale": "decisão registrada",
    }
    # still affected by the open blocking question: it must be blocked by it or state independence
    with pytest.raises(RefineError) as exc:
        refine_plan(backlog, {"author": {"agent": "a"}, "changes": [resolve, ready]})
    assert any("neither is blocked by it nor states why" in e for e in exc.value.errors)
    q1 = next(q["id"] for q in backlog["questions"] if q["blocking"])
    independent = copy.deepcopy(ready)
    independent["readiness"]["independent_of"] = [{"ref": q1, "rationale": "contrato confirmado pelo time"}]
    doc = refine_plan(backlog, {"author": {"agent": "a"}, "changes": [resolve, independent]})
    assert {c["key"] for c in doc["changes"]} == {"F1", "R1"}


def test_work_changed_after_review_is_not_cleared_in_a_team_plan() -> None:
    backlog = team._backlog()
    backlog["items"][1]["status"] = "draft"  # S1 changed by an evolution, not re-reviewed
    tp = plan(backlog, team._input())["team_plan"]
    assert tp["unreviewed"] == [team.S1]
    assert tp["g10"]["status"] == "BLOCKED" and "not re-reviewed" in tp["g10"]["reason"]


def test_old_schema_backlog_without_readiness_or_findings_plans_as_before() -> None:
    backlog = team._backlog()
    for i in backlog["items"]:
        i.pop("readiness", None)
    tp = plan(backlog, team._input())["team_plan"]
    assert tp["g10"]["status"] == "PASS" and disputed_items(backlog) == {}
    assert tp["unallocated"] == [{"item": team.S3, "reason": "not placed by the proposal"}]


def test_resolved_dispute_applies_and_stays_traceable(disputed: Any, tmp_path: Path) -> None:
    backlog, _ = disputed
    t6 = _id(backlog, "Fluxo do quiosque")
    finding = next(f for f in backlog["findings"] if t6 in f["affects"] and f["gate"] == "G08")
    change = {"key": "F1", "op": "resolve_finding", "target": finding["id"], "rationale": "revisado"}
    doc = refine_plan(backlog, {"author": {"agent": "a"}, "changes": [change]})
    result = refine_apply(backlog, doc, ["F1"], doc["plan_digest"])
    after = result[0] if isinstance(result, tuple) else result
    refined = after.get("backlog", after)
    resolved = next(f for f in refined["findings"] if f["id"] == finding["id"])
    assert resolved["review_status"] == "resolved" and resolved["evidence"][-1]["summary"] == "revisado"
    assert disputed_items(refined) == {}
