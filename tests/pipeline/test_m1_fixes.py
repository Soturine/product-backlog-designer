"""Regressions for defects found by the M1 dogfood (qualification ledger QL-001, QL-002, QL-004)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.design import compile_design, submit_claims, submit_design
from pbd.pipeline.finalize import finalize
from pbd.pipeline.review import submit_review
from pbd.pipeline.run import Run, normalize_request, start
from pbd.render.richtext import description_html
from tests.pipeline.helpers import claims_payload, design_payload, make_workspace, read_all
from tests.pipeline.test_review_finalize import review_payload


@pytest.fixture
def ambiguous_run(tmp_path: Path) -> Run:
    ws = make_workspace(tmp_path)
    run = start(
        tmp_path / "out",
        ws,
        [("prd.md", "functional"), ("decisoes", "decision")],
        normalize_request(synthetic=True),
    )
    read_all(run)
    payload = claims_payload(run)
    payload["claims"][2]["uncertainty"] = {"level": "ambiguous", "note": "list name only"}  # C3
    submit_claims(run, payload)
    return run


def _errors(run: Run, mutate: Any) -> list[str]:
    payload = design_payload()
    mutate(payload)
    errors, _ = compile_design(run, payload)
    return errors


def test_confirmed_criterion_on_ambiguous_claim_is_rejected(ambiguous_run: Run) -> None:
    errors = _errors(ambiguous_run, lambda p: None)  # AC4 is confirmed and traces only ambiguous C3
    assert any("AC4: confirmed criterion traces only ambiguous" in e for e in errors), errors

    def as_proposed(p: dict[str, Any]) -> None:
        p["criteria"][3].update(status="proposed", rationale="Lista citada sem regra; alternativa em Q1.")

    assert _errors(ambiguous_run, as_proposed) == []


def test_confirmed_field_on_ambiguous_claim_is_rejected(ambiguous_run: Run) -> None:
    def mutate(p: dict[str, Any]) -> None:
        p["criteria"][3].update(status="proposed", rationale="r")
        p["items"][3]["fields"] = {"priority": {"state": "confirmed", "value": 1, "claims": ["C3"]}}

    assert any("field priority is confirmed" in e for e in _errors(ambiguous_run, mutate))


def test_visible_criterion_ids_in_text_are_rejected(ambiguous_run: Run) -> None:
    def mutate(p: dict[str, Any]) -> None:
        p["criteria"][3].update(status="proposed", rationale="r")
        p["items"][4]["content"]["verification"] = "Demonstrar CA-02 com canteiro ocupado."

    errors = _errors(ambiguous_run, mutate)
    assert any("T1: references visible criterion ID CA-02" in e for e in errors), errors


def test_claims_only_in_containers_are_signalled(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path)
    run = start(
        tmp_path / "out",
        ws,
        [("prd.md", "functional"), ("decisoes", "decision")],
        normalize_request(synthetic=True),
    )
    read_all(run)
    submit_claims(run, claims_payload(run))
    payload = design_payload()
    payload["dispositions"][2] = {
        "claim": "C3",
        "status": "COVERED",
        "covered_by": ["F1"],
        "rationale": "rule",
    }
    payload["items"][1]["claims"].append("C3") if "C3" not in payload["items"][1]["claims"] else None
    submit_design(run, payload)
    submit_review(run, review_payload(run))
    finalize(run)
    checks = json.loads(run.path("output/checks.json").read_text(encoding="utf-8"))
    claims = {c["id"]: c for c in run.read("stages/claims.json")["claims"]}
    flagged = [claims[c]["key"] for c in checks["signals"]["claims_only_in_containers"]]
    assert flagged == ["C3"]


@pytest.mark.parametrize(
    ("want", "expected"),
    [
        ("que o sistema registrasse a rega", "<strong>gostaria que</strong> o sistema registrasse"),
        ("gostaria que o sistema registrasse a rega", "<strong>gostaria que</strong> o sistema registrasse"),
    ],
)
def test_repeated_connector_words_are_not_duplicated(want: str, expected: str) -> None:
    html = description_html(
        {"kind": "role_goal_benefit", "actor": "professor", "want": want, "benefit": "acompanhar"}, "pt-BR"
    )
    assert expected in html and "que que" not in html


def test_criterion_keys_in_text_are_rejected(ambiguous_run: Run) -> None:
    def mutate(p: dict[str, Any]) -> None:
        p["criteria"][3].update(status="proposed", rationale="r")
        p["items"][4]["content"]["verification"] = "Demonstrar AC2 com canteiro ocupado."

    errors = _errors(ambiguous_run, mutate)
    assert any("T1: mentions criterion key AC2" in e for e in errors), errors
