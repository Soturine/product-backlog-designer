"""Compare mode: two baselines, one shared independent inventory, many-to-many mappings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.compare import finalize_comparison, submit_comparison, validate_comparison
from pbd.pipeline.design import submit_claims
from pbd.pipeline.run import Run, RunError, normalize_request, start
from tests.pipeline.helpers import claims_payload, make_workspace, read_all, src_id
from tests.pipeline.test_review_finalize import INVEST_OK

SOURCES = [("prd.md", "functional"), ("decisoes", "decision")]
LEFT = {
    "kind": "pbd.import",
    "items": [
        {"id": "A1", "type": "Epic", "title": "Canteiros"},
        {
            "id": "A2",
            "type": "User Story",
            "title": "Reservar e listar",
            "parent": "A1",
            "acceptance_criteria": "<ul><li>Reserva de canteiro livre</li>"
            "<li>Lista Minhas reservas</li></ul>",
        },
    ],
}
RIGHT = {
    "kind": "pbd.import",
    "items": [
        {"id": "A1", "type": "Epic", "title": "Reservas"},
        {
            "id": "B2",
            "type": "User Story",
            "title": "Reservar canteiro",
            "parent": "A1",
            "acceptance_criteria": "- Reserva de canteiro livre\n- Canteiro ocupado é rejeitado",
        },
        {"id": "B3", "type": "User Story", "title": "Minhas reservas", "parent": "A1"},
        {"id": "B4", "type": "User Story", "title": "Pagar reserva", "parent": "A1"},
    ],
}


@pytest.fixture
def run(tmp_path: Path) -> Run:
    ws = make_workspace(tmp_path)
    (ws / "left.json").write_text(json.dumps(LEFT), encoding="utf-8")
    (ws / "right.json").write_text(json.dumps(RIGHT), encoding="utf-8")
    run = start(
        tmp_path / "out",
        ws,
        SOURCES,
        normalize_request(mode="compare", synthetic=True),
        baselines=["left.json", "right.json"],
    )
    read_all(run)
    out = submit_claims(run, claims_payload(run))
    assert out["baseline_compiled"]["left"]["items"] == 2 and out["baseline_compiled"]["right"]["items"] == 4
    return run


def payload(run: Run) -> dict[str, Any]:
    p, d = src_id(run, "prd.md"), src_id(run, "decisoes")
    ok = {"verdict": "pass", "source_support": "supported"}
    story = {**ok, "invest": {**INVEST_OK}, "task_sufficiency": "not_applicable"}

    def ob(
        key: str,
        quote: str,
        line: int,
        left: tuple[str, list[str]],
        right: tuple[str, list[str]],
        src: str = p,
        member: str = "prd.md",
    ) -> dict[str, Any]:
        return {
            "key": key,
            "text": quote,
            "quote": quote,
            "locator": {"source_id": src, "member": member, "line_start": line},
            "matched_claims": [],
            "left": {"disposition": left[0], "covered_by": left[1], "rationale": "r"},
            "right": {"disposition": right[0], "covered_by": right[1], "rationale": "r"},
        }

    return {
        "reviewer": {"agent": "comparer", "model": "test-model", "independence": "separate_agent"},
        "sources_reread": [{"source_id": p, "complete": True}, {"source_id": d, "complete": True}],
        "independent_obligations": [
            ob(
                "O1",
                "pode reservar um canteiro livre",
                4,
                ("COVERED", ["L-A2.AC1"]),
                ("COVERED", ["R-B2.AC1"]),
            ),
            ob("O2", "não aceita nova reserva", 5, ("NOT_COVERED", []), ("COVERED", ["R-B2.AC2"])),
            ob("O3", "Minhas reservas", 6, ("COVERED", ["L-A2.AC2"]), ("PARTIALLY_COVERED", ["R-B3"])),
            ob(
                "O5",
                "confirmadas automaticamente",
                3,
                ("NOT_COVERED", []),
                ("NOT_COVERED", []),
                d,
                "adr-001.md",
            ),
        ],
        "items": [
            {"key": "L-A1", **ok},
            {"key": "L-A2", **story},
            {"key": "R-A1", **ok},
            {"key": "R-B2", **story},
            {"key": "R-B3", **story},
            {
                "key": "R-B4",
                "verdict": "fail",
                "source_support": "unsupported",
                "notes": "fora do escopo",
                "invest": {**INVEST_OK},
                "task_sufficiency": "not_applicable",
            },
        ],
        "criteria": [{"key": k, **ok} for k in ("L-A2.AC1", "L-A2.AC2", "R-B2.AC1", "R-B2.AC2")],
        "mappings": [
            {"left": ["L-A1"], "right": ["R-A1"], "relation": "equivalent", "rationale": "mesmo épico"},
            {
                "left": ["L-A2"],
                "right": ["R-B2", "R-B3"],
                "relation": "split",
                "rationale": "uma história vs duas",
                "differences": ["rejeição só na direita"],
            },
        ],
        "findings": [
            {
                "classification": "confirmed_gap",
                "severity": "high",
                "side": "left",
                "expected": "Rejeitar canteiro ocupado.",
                "actual": "Sem critério.",
                "why": "PRD 2.2.",
                "impact": "Reserva dupla.",
                "recommendation": "Adicionar critério.",
                "affects": ["L-A2"],
            },
            {
                "classification": "unsupported_assumption",
                "severity": "medium",
                "side": "right",
                "expected": "Pagamentos fora.",
                "actual": "História de pagamento.",
                "why": "PRD 3.",
                "impact": "Escopo extra.",
                "recommendation": "Remover.",
                "affects": ["R-B4"],
            },
        ],
    }


def test_compare_requires_two_baselines(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path)
    (ws / "left.json").write_text(json.dumps(LEFT), encoding="utf-8")
    with pytest.raises(RunError, match="compare requires two"):
        start(tmp_path / "o", ws, SOURCES, normalize_request(mode="compare"), baselines=["left.json"])


def test_comparison_contract_rejects_incomplete_or_unknown(run: Run) -> None:
    bad = payload(run)
    bad["items"].pop()
    bad["mappings"].append({"left": ["L-ZZ"], "right": [], "relation": "same", "rationale": ""})
    bad["independent_obligations"][0]["right"]["covered_by"] = ["L-A2"]
    bad["findings"][0]["side"] = "middle"
    errors = validate_comparison(run, bad)
    assert any("exactly once" in e for e in errors)
    assert any("mappings[2]: left" in e for e in errors) and any("relation must be" in e for e in errors)
    assert any("independent_obligations[0].right: unknown keys" in e for e in errors)
    assert any("side must be" in e for e in errors)


def test_comparison_finalizes_with_shared_denominator(run: Run) -> None:
    submit_comparison(run, payload(run))
    result = finalize_comparison(run)
    doc = json.loads(run.path("output/comparison.json").read_text("utf-8"))
    left, right = doc["sides"]["left"], doc["sides"]["right"]
    assert left["coverage"]["denominator"] == right["coverage"]["denominator"] == 4
    assert (left["coverage"]["covered"], right["coverage"]["covered"]) == (2, 2)
    assert right["coverage"]["partially_covered"] == 1
    assert doc["mapping_cardinality"] == {"1:1": 1, "1:N": 1}
    assert right["unmatched_items"] == ["R-B4"] and right["unsupported"] == ["R-B4"]
    assert [o["agreement"] for o in doc["obligations"]] == ["same", "differs", "differs", "same"]
    assert not {"winner", "score"} & set(doc)
    html = run.path("output/report.html").read_text("utf-8")
    assert "Comparação de backlogs" in html and "L-A2" in html and result["mappings"] == 2
