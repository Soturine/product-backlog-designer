"""check, clarify, profile inference, refinement and execution profiles."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from pbd.cli import main
from pbd.core.execution import execution_profile
from pbd.pipeline import refine
from pbd.pipeline.finalize import finalize
from pbd.pipeline.modes import check, clarify, clarify_markdown, infer_profile
from pbd.pipeline.review import submit_review
from pbd.pipeline.run import RunError, normalize_request
from pbd.profiles import validate_profile
from tests.pipeline.helpers import designed_run
from tests.pipeline.test_review_finalize import review_payload

CSV = (
    "id,type,title,parent,acceptance_criteria,priority\n"
    "1,Epic,Billing,,,\n"
    '2,User Story,Pay invoice,1,"Scenario: ok\nGiven a\nThen b",1\n'
    "3,User Story,Pay  invoice!,1,,2\n"
    "4,Task,Build form,2,,\n"
    "5,Task,Sub of task,4,,\n"
)


@pytest.fixture(scope="module")
def backlog_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("final")
    run = designed_run(tmp, title="Horta")
    submit_review(run, review_payload(run))
    finalize(run)
    return run.path("output/backlog.json")


def test_check_is_structural_and_never_overclaims(tmp_path: Path) -> None:
    p = tmp_path / "b.csv"
    p.write_text(CSV, encoding="utf-8")
    out = check(p)
    assert out["scope"] == "structural_only" and "not assessed" in out["scope_note"]
    codes = {(w["code"], w["item"]) for w in out["warnings"]}
    assert ("story_without_criteria", "3") in codes and ("child_of_task", "5") in codes
    assert out["duplicate_title_candidates"] == [["2", "3"]]  # candidates only
    assert out["status"] == "warn" and out["errors"] == []


def test_check_validates_canonical_backlogs(backlog_file: Path, tmp_path: Path) -> None:
    assert check(backlog_file)["status"] in ("pass", "warn")
    doc = json.loads(backlog_file.read_text(encoding="utf-8"))
    doc["items"][1]["parent"] = "PBD-EPIC-000000000000"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["check", str(bad)]) != 0


def test_clarify_lists_open_questions_first_blocking(backlog_file: Path) -> None:
    doc = json.loads(backlog_file.read_text(encoding="utf-8"))
    out = clarify(doc)
    assert out["summary"]["open_questions"] == len([q for q in doc["questions"] if q["status"] == "open"])
    assert all(a["item_title"] for q in out["questions"] for a in q["affects"])
    md = clarify_markdown(out)
    assert md.startswith("# Clarifications") and "become decisions only when recorded" in md


def test_profile_inference_is_a_reviewed_draft(tmp_path: Path) -> None:
    p = tmp_path / "b.csv"
    p.write_text(CSV, encoding="utf-8")
    out = infer_profile(p, profile_id="Team X")
    draft = out["draft_profile"]
    assert out["status"] == "proposed" and draft["verified"] is False and draft["id"] == "team-x"
    assert draft["types"]["story"] == "User Story" and draft["types"]["bug"] is None
    assert {"parent": "Epic", "child": "User Story", "count": 2} in out["observed"]["hierarchy_pairs"]
    assert out["observed"]["dominant_acceptance_style"] == "gherkin"
    assert validate_profile(draft) == [] and out["draft_problems"] == []


def _proposal(doc: dict[str, Any]) -> dict[str, Any]:
    story = next(i for i in doc["items"] if i["type"] == "story")
    crit = next(c for c in doc["criteria"] if c["parent"] == story["id"])
    claim = story["claim_refs"][0]
    return {
        "author": {"agent": "refiner", "model": "test-model"},
        "changes": [
            {
                "key": "R1",
                "op": "update_title",
                "target": story["id"],
                "value": "Reservar canteiro",
                "rationale": "mais curto",
            },
            {
                "key": "R2",
                "op": "add_criterion",
                "target": story["id"],
                "expected_outcomes": ["Mensagem de erro clara"],
                "rationale": "fluxo de erro sem critério",
            },
            {
                "key": "R3",
                "op": "set_criterion_status",
                "target": crit["id"],
                "status": "superseded",
                "rationale": "substituído por decisão",
            },
            {
                "key": "R4",
                "op": "set_field",
                "target": story["id"],
                "field": "priority",
                "state": "confirmed",
                "value": 1,
                "claim_refs": [claim],
                "rationale": "fonte declara prioridade",
            },
        ],
    }


def test_refine_plans_diffs_and_applies_only_approved(backlog_file: Path) -> None:
    doc = json.loads(backlog_file.read_text(encoding="utf-8"))
    plan = refine.plan(doc, _proposal(doc))
    assert [c["key"] for c in plan["changes"]] == ["R1", "R2", "R3", "R4"] and plan["status"] == "proposed"
    md = refine.diff_markdown(plan, doc)
    assert "nothing applied" in md and "R3" in md
    res = refine.apply(doc, plan, ["R1", "R2"], plan["plan_digest"])
    out = res["backlog"]
    story = next(i for i in out["items"] if i["title"] == "Reservar canteiro")
    assert story["status"] == "draft"
    added = [c for c in out["criteria"] if c["origin"] == "human_edited"]
    assert len(added) == 1 and added[0]["status"] == "proposed"  # no claim refs → proposed, not confirmed
    assert res["result"]["applied"] == ["R1", "R2"] and res["result"]["skipped"] == ["R3", "R4"]
    assert len(out["items"]) == len(doc["items"]) and len(out["criteria"]) == len(doc["criteria"]) + 1


def test_refine_refuses_deletion_forbidden_fields_tampering_and_stale_base(backlog_file: Path) -> None:
    doc = json.loads(backlog_file.read_text(encoding="utf-8"))
    story = next(i for i in doc["items"] if i["type"] == "story")
    bad = {
        "author": {"agent": "a"},
        "changes": [
            {"key": "D", "op": "delete_item", "target": story["id"], "rationale": "x"},
            {
                "key": "F",
                "op": "set_field",
                "target": story["id"],
                "field": "assigned_to",
                "value": "x",
                "rationale": "x",
            },
            {
                "key": "C",
                "op": "set_field",
                "target": story["id"],
                "field": "priority",
                "state": "confirmed",
                "value": 1,
                "rationale": "sem evidência",
            },
        ],
    }
    with pytest.raises(refine.RefineError) as err:
        refine.plan(doc, bad)
    text = "\n".join(err.value.errors)
    assert (
        "deletion is not a refinement" in text and "never set by PBD" in text and "needs claim_refs" in text
    )
    plan = refine.plan(doc, _proposal(doc))
    tampered = copy.deepcopy(plan)
    tampered["changes"][0]["after"] = "outro"
    with pytest.raises(refine.RefineError, match="refinement not applied"):
        refine.apply(doc, tampered, ["all"], plan["plan_digest"])
    changed = copy.deepcopy(doc)
    changed["items"][0]["title"] = "editado por outra pessoa"
    with pytest.raises(refine.RefineError) as err2:
        refine.apply(changed, plan, ["all"], plan["plan_digest"])
    assert "conflict" in "\n".join(err2.value.errors)


def test_refine_cli_round_trip(
    backlog_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = json.loads(backlog_file.read_text(encoding="utf-8"))
    prop = tmp_path / "p.json"
    prop.write_text(json.dumps(_proposal(doc)), encoding="utf-8")
    assert (
        main(["refine", "plan", "--backlog", str(backlog_file), "--file", str(prop), "--out", str(tmp_path)])
        == 0
    )
    digest_ = json.loads(capsys.readouterr().out)["plan_digest"]
    assert (tmp_path / "refinement-diff.md").exists()
    args = [
        "refine",
        "apply",
        "--backlog",
        str(backlog_file),
        "--plan",
        str(tmp_path / "refinement-plan.json"),
        "--approve",
        "all",
        "--plan-digest",
        digest_,
        "--out",
        str(tmp_path),
    ]
    assert main(args) == 0
    refined = json.loads((tmp_path / "backlog.refined.json").read_text(encoding="utf-8"))
    assert any(c["status"] == "superseded" for c in refined["criteria"])


def test_execution_profiles_are_portable() -> None:
    for name in ("economical", "balanced", "rigorous"):
        prof = execution_profile(name)
        assert set(prof["tiers"].values()) <= {"economy", "standard", "strong"}
        assert "sequential_role" in prof["fallback"]
    assert execution_profile("economical")["max_concurrent_agents"] == 1
    assert normalize_request(execution="rigorous")["execution"] == "rigorous"
    with pytest.raises(RunError):
        normalize_request(execution="turbo")


def test_refine_add_item_is_a_justified_proposal(backlog_file: Path) -> None:
    doc = json.loads(backlog_file.read_text(encoding="utf-8"))
    epic = next(i for i in doc["items"] if i["type"] == "epic")
    prop = {
        "author": {"agent": "refiner"},
        "changes": [
            {
                "key": "N1",
                "op": "add_item",
                "type": "feature",
                "parent": epic["id"],
                "title": "Notificações",
                "description": "<p>Avisar o membro</p><script>x</script>",
                "rationale": "proposta técnica",
            }
        ],
    }
    plan = refine.plan(doc, prop)
    out = refine.apply(doc, plan, ["all"], plan["plan_digest"])["backlog"]
    added = next(i for i in out["items"] if i["title"] == "Notificações")
    assert added["origin"] == "human_edited" and added["technical_rationale"] == "proposta técnica"
    assert "<script>" not in added["description"]["value"]
