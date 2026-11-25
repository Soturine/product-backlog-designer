"""M4 planning: no invented capacity, dates, estimates or scores; zero is not absence."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from pbd.pipeline.planning import PlanningError, is_stale, plan, plan_markdown


def _item(n: int, itype: str = "story", parent: str | None = None, **fields: Any) -> dict[str, Any]:
    return {
        "id": f"PBD-STORY-{n:012d}" if itype == "story" else f"PBD-EPIC-{n:012d}",
        "type": itype,
        "title": f"Item {n}",
        "parent": parent,
        "claim_refs": [],
        "origin": "generated",
        "status": "reviewed",
        "fields": {k: v for k, v in fields.items()},
    }


def _sp(value: Any, state: str = "confirmed") -> dict[str, Any]:
    return {"state": state, "value": value}


def _backlog() -> dict[str, Any]:
    epic = _item(1, "epic")
    a = _item(
        2,
        parent=epic["id"],
        story_points=_sp(5),
        priority=_sp(2),
        business_value=_sp(8),
        time_criticality=_sp(5),
        risk=_sp(3),
    )
    b = _item(3, parent=epic["id"], story_points=_sp(3), priority=_sp(1))
    c = _item(4, parent=epic["id"], story_points=_sp(0), priority=_sp(1))  # zero is a real estimate
    d = _item(5, parent=epic["id"], priority=_sp(3))  # no estimate
    e = _item(6, parent=epic["id"], story_points=_sp(13, "proposed"))
    f = _item(7, parent=epic["id"], original_estimate=_sp(16))  # hours only
    return {
        "run_id": "PBD-RUN-000000000000",
        "items": [epic, a, b, c, d, e, f],
        "criteria": [],
        "relations": [
            {
                "id": "PBD-REL-000000000001",
                "type": "predecessor",
                "source": a["id"],
                "target": b["id"],
                "status": "confirmed",
                "reason": "b needs a",
            },
        ],
    }


def test_without_capacity_there_is_only_a_sequence() -> None:
    doc = plan(_backlog())
    assert doc["sprints"] is None and doc["committed"] is False and doc["status"] == "proposal"
    assert any("not a sprint plan" in n for n in doc["notes"])
    seq = [x["item"] for x in doc["sequence"]]
    assert seq.index("PBD-STORY-000000000002") < seq.index("PBD-STORY-000000000003")  # dependency respected
    assert "PBD-EPIC-000000000001" not in seq  # containers are not scheduled
    assert "dates" not in str(doc["sprints"])


def test_zero_absent_proposed_and_units_are_distinct() -> None:
    doc = plan(_backlog(), {"capacity": {"unit": "story_points", "per_sprint": 8}})
    seq = {x["item"]: x for x in doc["sequence"]}
    assert seq["PBD-STORY-000000000004"]["effort"] == 0
    assert (
        seq["PBD-STORY-000000000005"]["effort"] is None
        and seq["PBD-STORY-000000000005"]["provenance"]["effort"] == "absent"
    )
    assert seq["PBD-STORY-000000000006"]["provenance"]["effort"] == "proposed_not_used"
    assert "units are not converted" in seq["PBD-STORY-000000000007"]["provenance"]["effort"]
    assert doc["checks"]["zero_estimates"] == ["PBD-STORY-000000000004"]
    reasons = {u["item"]: u["reason"] for u in doc["unplanned"]}
    assert reasons["PBD-STORY-000000000005"] == "estimate unknown"
    assert reasons["PBD-STORY-000000000007"] == "estimate unknown"
    with_proposed = plan(
        _backlog(), {"capacity": {"unit": "story_points", "per_sprint": 8}, "use_proposed_estimates": True}
    )
    over = {u["item"]: u["reason"] for u in with_proposed["unplanned"]}
    assert "split needed" in over["PBD-STORY-000000000006"]  # 13 > 8


def test_sprints_respect_dependencies_capacity_and_calendar() -> None:
    doc = plan(
        _backlog(),
        {
            "capacity": {"unit": "story_points", "per_sprint": 8, "sprints": 3},
            "calendar": {"start": "2027-01-04", "sprint_days": 14},
        },
    )
    sprint_of = {i: s["index"] for s in doc["sprints"] for i in s["items"]}
    assert sprint_of["PBD-STORY-000000000003"] > sprint_of["PBD-STORY-000000000002"]
    assert all(s["load"] <= s["capacity"] for s in doc["sprints"])
    assert doc["sprints"][0]["dates"] == {
        "start": "2027-01-04",
        "end": "2027-01-17",
        "derived_from": "user calendar",
    }
    md = plan_markdown(doc)
    assert md.startswith("# Sprint plan (proposal — not committed)")


def test_hours_plan_uses_original_estimate_only() -> None:
    doc = plan(_backlog(), {"capacity": {"unit": "hours", "per_sprint": 40}})
    planned = {i for s in doc["sprints"] for i in s["items"]}
    assert planned == {"PBD-STORY-000000000007"}


def test_scores_need_every_input() -> None:
    doc = plan(_backlog(), {"technique": "wsjf", "capacity": {"unit": "story_points", "per_sprint": 20}})
    seq = {x["item"]: x for x in doc["sequence"]}
    assert seq["PBD-STORY-000000000002"]["score"] == round((8 + 5 + 3) / 5, 4)
    assert "business_value" in doc["score_missing_inputs"]["PBD-STORY-000000000003"]
    assert seq["PBD-STORY-000000000003"]["score"] is None
    moscow = plan(
        _backlog(),
        {"technique": "moscow", "technique_inputs": {"PBD-STORY-000000000006": {"moscow": "must"}}},
    )
    assert moscow["sequence"][0]["item"] == "PBD-STORY-000000000006"
    rice = plan(
        _backlog(),
        {
            "technique": "rice",
            "technique_inputs": {
                "PBD-STORY-000000000004": {"reach": 100, "impact": 2, "confidence": 0.5, "effort": 0}
            },
        },
    )
    assert rice["score_missing_inputs"]["PBD-STORY-000000000004"] == ["effort > 0"]


def test_cycles_invalid_relations_blockers_and_cross_team() -> None:
    b = _backlog()
    b["relations"] += [
        {
            "id": "PBD-REL-000000000002",
            "type": "predecessor",
            "source": "PBD-STORY-000000000003",
            "target": "PBD-STORY-000000000002",
            "status": "proposed",
            "reason": "loop",
        },
        {
            "id": "PBD-REL-000000000003",
            "type": "predecessor",
            "source": "PBD-STORY-999999999999",
            "target": "PBD-STORY-000000000002",
            "status": "confirmed",
            "reason": "ghost",
        },
        {
            "id": "PBD-REL-000000000004",
            "type": "external_blocker",
            "source": "PBD-STORY-000000000005",
            "target": "vendor API contract",
            "status": "confirmed",
            "reason": "waits for vendor",
        },
    ]
    doc = plan(b, {"teams": {"PBD-STORY-000000000002": "a", "PBD-STORY-000000000003": "b"}})
    assert doc["checks"]["cycles"] and any("cycle" in n for n in doc["notes"])
    assert (
        doc["checks"]["invalid_relations"]
        and doc["checks"]["external_blockers"][0]["blocker"] == "vendor API contract"
    )
    ok = plan(_backlog(), {"teams": {"PBD-STORY-000000000002": "a", "PBD-STORY-000000000003": "b"}})
    assert ok["checks"]["cross_team_dependencies"][0]["other_team"] == "a"


def test_invalid_inputs_and_scenarios_and_staleness() -> None:
    with pytest.raises(PlanningError) as err:
        plan(
            _backlog(),
            {
                "capacity": {"unit": "days", "per_sprint": 0},
                "calendar": {"start": "soon", "sprint_days": 0},
                "technique": "magic",
            },
        )
    text = "\n".join(err.value.errors)
    assert (
        "capacity.unit" in text and "positive number" in text and "ISO date" in text and "technique" in text
    )
    with pytest.raises(PlanningError, match="calendar needs"):
        plan(_backlog(), {"calendar": {"start": "2027-01-04", "sprint_days": 14}})
    doc = plan(
        _backlog(),
        {
            "capacity": {"unit": "story_points", "per_sprint": 8},
            "scenarios": [{"name": "lower", "per_sprint": 5}],
        },
    )
    assert doc["scenarios"][0]["committed"] is False and doc["scenarios"][0]["sprints"] >= len(doc["sprints"])
    changed = copy.deepcopy(_backlog())
    changed["items"][1]["title"] = "renamed"
    assert not is_stale(doc, _backlog()) and is_stale(doc, changed)


def test_plan_cli_writes_report_and_detects_staleness(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from pbd.cli import main

    backlog = {**_backlog(), "kind": "pbd.backlog", "language": "pt-BR"}
    (tmp_path / "b.json").write_text(json.dumps(backlog), encoding="utf-8")
    (tmp_path / "i.json").write_text(
        json.dumps({"capacity": {"unit": "story_points", "per_sprint": 8}}), encoding="utf-8"
    )
    out = tmp_path / "o"
    assert (
        main(
            [
                "plan",
                "--backlog",
                str(tmp_path / "b.json"),
                "--input",
                str(tmp_path / "i.json"),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    page = (out / "plan-report.html").read_text(encoding="utf-8")
    assert "Quadro de sprints" in page and "Não planejado" in page and "estimate unknown" in page
    assert (
        main(
            ["plan", "check", "--backlog", str(tmp_path / "b.json"), "--plan", str(out / "sprint-plan.json")]
        )
        == 0
    )
    backlog["items"][1]["title"] = "mudou"
    (tmp_path / "b.json").write_text(json.dumps(backlog), encoding="utf-8")
    assert (
        main(
            ["plan", "check", "--backlog", str(tmp_path / "b.json"), "--plan", str(out / "sprint-plan.json")]
        )
        == 1
    )
    capsys.readouterr()
