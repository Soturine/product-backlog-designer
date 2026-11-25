from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.design import compile_design, submit_claims, submit_design
from pbd.pipeline.run import Run, RunError, normalize_request, start
from pbd.validation.invariants import check_backlog
from pbd.validation.schema import validate
from tests.pipeline.helpers import claims_payload, design_payload, designed_run, make_workspace, read_all


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
    return run


def test_claims_account_for_every_obligation(read_run: Run) -> None:
    payload = claims_payload(read_run)
    payload["claims"].pop()  # drop C6 (X1 unaccounted)
    with pytest.raises(RunError) as exc:
        submit_claims(read_run, payload)
    assert any("not accounted" in e for e in exc.value.errors)
    payload = claims_payload(read_run)
    payload["claims"][1]["sources"].append(payload["claims"][0]["sources"][0])
    with pytest.raises(RunError) as exc:
        submit_claims(read_run, payload)
    assert any("more than once" in e for e in exc.value.errors)
    assert read_run.stage_status("claims") == "pending"


def test_claims_reject_unknown_refs_and_unapproved_supersession(read_run: Run) -> None:
    payload = claims_payload(read_run)
    payload["claims"][0]["sources"] = ["PBD-SRC-000000000000:R9"]
    with pytest.raises(RunError):
        submit_claims(read_run, payload)
    payload = claims_payload(read_run)
    payload["decisions"][0]["status"] = "proposed"
    with pytest.raises(RunError) as exc:
        submit_claims(read_run, payload)
    assert any("only an approved decision" in e for e in exc.value.errors)


def test_claims_carry_verified_locators_and_supersession(read_run: Run) -> None:
    submit_claims(read_run, claims_payload(read_run))
    doc = read_run.read("stages/claims.json")
    c4 = next(c for c in doc["claims"] if c["key"] == "C4")
    assert c4["temporal"]["status"] == "superseded" and c4["disposition"]["status"] == "SUPERSEDED"
    assert doc["decisions"][0]["supersedes_claims"] == [c4["id"]]
    loc = doc["claims"][0]["evidence"][0]["locator"]
    assert loc["member"] == "prd.md" and loc["line_start"] == 4 and loc["quote_digest"].startswith("sha256:")


def test_design_compiles_to_valid_canonical_backlog(tmp_path: Path) -> None:
    run = designed_run(tmp_path)
    backlog = run.read("stages/backlog.draft.json")
    clean = {k: v for k, v in backlog.items() if k != "keys"}
    assert validate("backlog", clean) == [] and check_backlog(clean) == []
    story = next(i for i in backlog["items"] if i["title"] == "Reservar um canteiro livre")
    assert story["description"]["value"].startswith("<p><strong>Eu como</strong> membro")
    assert story["fields"]["story_points"]["state"] == "proposed"
    crits = [c for c in backlog["criteria"] if c["parent"] == story["id"]]
    assert [c["visible_id"] for c in crits] == ["CA-01", "CA-02", "CA-03"]
    assert run.stage_status("design") == "complete"
    assert backlog["keys"][story["id"]] == "US1"


def _compile(run: Run, mutate: Any) -> list[str]:
    payload = design_payload()
    mutate(payload)
    errors, _ = compile_design(run, payload)
    return errors


@pytest.fixture
def claimed_run(read_run: Run) -> Run:
    submit_claims(read_run, claims_payload(read_run))
    return read_run


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p["dispositions"].pop(0), "disposition required"),
        (lambda p: p["items"][2]["claims"].append("C4"), "inactive claim"),
        (
            lambda p: p["items"][2]["fields"].update(
                assigned_to={"state": "proposed", "value": "x", "rationale": "y"}
            ),
            "never generated",
        ),
        (lambda p: p["items"][2].update(content={"kind": "task", "summary": "x"}), "does not fit"),
        (lambda p: p["items"][4].update(parent=None), "requires a parent"),
        (lambda p: p["criteria"][0].update(claims=["C3"]), "absent from parent"),
        (lambda p: p["criteria"][0].update(parent="T1"), "cannot own acceptance"),
        (lambda p: p["criteria"][2].update(claims=[]), "claim_refs"),
        (lambda p: p["items"][0].update(key="US1"), "duplicate key"),
        (lambda p: p["dispositions"][0].update(covered_by=["AC2"]), "trace back"),
        (lambda p: p["items"][3].update(claims=[]), "technical_rationale"),
        (lambda p: p["questions"][0].update(affects=["NOPE"]), "unknown affected"),
    ],
)
def test_design_rejections(claimed_run: Run, mutate: Any, message: str) -> None:
    errors = _compile(claimed_run, mutate)
    assert any(message in e for e in errors), errors


def test_templated_items_rejected(claimed_run: Run) -> None:
    def mutate(p: dict[str, Any]) -> None:
        for i in range(3):
            p["items"].append(
                {
                    "key": f"T{i + 10}",
                    "type": "task",
                    "title": f"Tarefa {i}",
                    "parent": "US1",
                    "claims": ["C2"],
                    "content": {"kind": "task", "summary": f"Implementar item {i} padrão"},
                }
            )

    assert any("templated" in e for e in _compile(claimed_run, mutate))


def test_selective_levels_enforced(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path)
    run = start(
        tmp_path / "out",
        ws,
        [("prd.md", "functional"), ("decisoes", "decision")],
        normalize_request(levels=["stories", "acceptance"], synthetic=True),
    )
    read_all(run)
    submit_claims(run, claims_payload(run))
    errors, _ = compile_design(run, design_payload())
    assert any("outside the requested levels" in e for e in errors)

    payload = design_payload()
    payload["items"] = [copy.deepcopy(i) for i in payload["items"] if i["type"] == "story"]
    for item in payload["items"]:
        item["parent"] = None
    payload["dispositions"][1]["covered_by"] = ["AC2"]
    submit_design(run, payload)
    backlog = run.read("stages/backlog.draft.json")
    assert {i["type"] for i in backlog["items"]} == {"story"}


def test_design_requires_claims_stage(read_run: Run) -> None:
    with pytest.raises(RunError, match="claims"):
        submit_design(read_run, design_payload())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda c: c.update(uncertainty={"level": "conflicting", "conflicts_with": ["C2"]}),
            "only level and note",
        ),
        (lambda c: c.update(uncertainty={"level": "maybe"}), "uncertainty.level"),
        (lambda c: c.update(category="wish"), "category"),
        (lambda c: c.update(priority="high"), "unknown fields"),
    ],
)
def test_claims_rejected_at_submission_not_later(read_run: Run, mutate: Any, message: str) -> None:
    """Regression (dogfood c05): a claim shape the design stage refuses must be rejected at claims time."""
    payload = claims_payload(read_run)
    mutate(payload["claims"][0])
    with pytest.raises(RunError) as exc:
        submit_claims(read_run, payload)
    assert any(message in e for e in exc.value.errors), exc.value.errors
    assert read_run.stage_status("claims") == "pending"
