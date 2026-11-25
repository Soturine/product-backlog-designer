"""Audit mode: imported baseline replaces design; the independent review audits it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbd.cli import main
from pbd.pipeline.design import submit_claims, submit_design
from pbd.pipeline.finalize import finalize
from pbd.pipeline.review import submit_review
from pbd.pipeline.run import Run, RunError, normalize_request, start
from tests.pipeline.helpers import claims_payload, design_payload, make_workspace, read_all, src_id
from tests.pipeline.test_review_finalize import INVEST_OK

SOURCES = [("prd.md", "functional"), ("decisoes", "decision")]
BASELINE = {
    "kind": "pbd.import",
    "items": [
        {"id": "100", "type": "Epic", "title": "Canteiros"},
        {
            "id": "101",
            "type": "User Story",
            "title": "Reservar canteiro",
            "parent": "100",
            "acceptance_criteria": "<ul><li>Membro reserva canteiro livre</li>"
            "<li>Coordenação aprova manualmente cada reserva</li></ul>",
            "fields": {"priority": 1, "assigned_to": "someone"},
        },
        {"id": "102", "type": "User Story", "title": "Pagar reserva", "parent": "100"},
    ],
}


def _audit_run(tmp_path: Path) -> Run:
    ws = make_workspace(tmp_path)
    (ws / "baseline.json").write_text(json.dumps(BASELINE), encoding="utf-8")
    req = normalize_request(mode="audit", synthetic=True)
    run = start(tmp_path / "out", ws, SOURCES, req, baselines=["baseline.json"])
    read_all(run)
    result = submit_claims(run, claims_payload(run))
    assert result["baseline_compiled"]["items"] == 3
    return run


def _audit_review(run: Run) -> dict[str, Any]:
    p, d = src_id(run, "prd.md"), src_id(run, "decisoes")
    ok = {"verdict": "pass", "source_support": "supported"}
    ob = lambda k, q, line, disp, **kw: {  # noqa: E731
        "key": k,
        "text": q,
        "quote": q,
        "locator": {
            "source_id": d if k == "O5" else p,
            "member": "adr-001.md" if k == "O5" else "prd.md",
            "line_start": line,
        },
        "disposition": disp,
        "rationale": "audit",
        **kw,
    }
    return {
        "reviewer": {"agent": "auditor", "model": "test-model", "independence": "separate_agent"},
        "sources_reread": [{"source_id": p, "complete": True}, {"source_id": d, "complete": True}],
        "independent_obligations": [
            ob(
                "O1",
                "pode reservar um canteiro livre",
                4,
                "COVERED",
                matched_claims=["C1"],
                covered_by=["I101.AC1"],
            ),
            ob("O2", "não aceita nova reserva", 5, "NOT_COVERED", matched_claims=["C2"]),
            ob("O3", "Minhas reservas", 6, "NOT_COVERED", matched_claims=["C3"]),
            ob("O4", "aprovadas manualmente", 7, "SUPERSEDED", matched_claims=["C4"]),
            ob("O5", "confirmadas automaticamente", 3, "NOT_COVERED", matched_claims=["C5"]),
        ],
        "items": [
            {"key": "I100", **ok},
            {"key": "I101", **ok, "invest": {**INVEST_OK}, "task_sufficiency": "not_applicable"},
            {
                "key": "I102",
                "verdict": "fail",
                "source_support": "unsupported",
                "notes": "payments are out of scope",
                "invest": {**INVEST_OK},
                "task_sufficiency": "not_applicable",
            },
        ],
        "criteria": [
            {"key": "I101.AC1", **ok},
            {
                "key": "I101.AC2",
                "verdict": "fail",
                "source_support": "unsupported",
                "notes": "superseded by ADR",
            },
        ],
        "duplicates": [],
        "dependencies_reviewed": True,
        "findings": [
            {
                "gate": "G04",
                "classification": "confirmed_divergence",
                "severity": "high",
                "expected": "Reservas válidas confirmadas automaticamente (ADR-001).",
                "actual": "Critério exige aprovação manual.",
                "why": "A ADR aprovada substitui a aprovação manual.",
                "impact": "Fluxo implementado contraria a decisão vigente.",
                "recommendation": "Substituir o critério pela confirmação automática.",
                "affects": ["I101.AC2", "C5"],
            },
            {
                "gate": "G09",
                "classification": "unsupported_assumption",
                "severity": "medium",
                "expected": "Pagamentos fora do escopo.",
                "actual": "História de pagamento no backlog.",
                "why": "PRD exclui pagamentos.",
                "impact": "Escopo indevido.",
                "recommendation": "Remover ou mover para fora do escopo após decisão.",
                "affects": ["I102"],
            },
        ],
    }


def test_audit_requires_baseline_and_rejects_unmapped_types(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path)
    with pytest.raises(RunError, match="audit requires --baseline"):
        start(tmp_path / "out", ws, SOURCES, normalize_request(mode="audit"))
    (ws / "b.json").write_text(
        json.dumps({"kind": "pbd.import", "items": [{"id": "1", "type": "Initiative", "title": "x"}]}),
        encoding="utf-8",
    )
    with pytest.raises(RunError, match="unmapped"):
        start(tmp_path / "out", ws, SOURCES, normalize_request(mode="audit"), baselines=["b.json"])
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").rglob("manifest.json"))


def test_audit_compiles_baseline_without_inventing_trace(tmp_path: Path) -> None:
    run = _audit_run(tmp_path)
    draft = run.read("stages/backlog.draft.json")
    assert {i["origin"] for i in draft["items"]} == {"imported"}
    assert all(i["claim_refs"] == [] for i in draft["items"] + draft["criteria"])
    story = next(i for i in draft["items"] if i["title"] == "Reservar canteiro")
    assert story["fields"] == {
        "priority": {
            "state": "proposed",
            "value": 1,
            "rationale": "imported baseline value",
            "review_status": "unreviewed",
        }
    }
    assert story["external_refs"][0]["native_id"] == "101"
    assert [c["raw"] for c in draft["criteria"]][1].startswith("Coordenação aprova")
    with pytest.raises(RunError, match="design is complete"):
        submit_design(run, design_payload())
    order = run.write_work_order()
    assert order["next_stage"] == "independent_review" and "AUDIT" in order["instruction"]


def test_audit_finalizes_with_honest_gates(tmp_path: Path) -> None:
    run = _audit_run(tmp_path)
    submit_review(run, _audit_review(run))
    result = finalize(run)
    gates = {
        g["id"]: g["status"] for g in json.loads(run.path("output/gates.json").read_text("utf-8"))["gates"]
    }
    assert gates["G02"] == "FAIL"  # baseline leaves obligations uncovered
    assert gates["G09"] == "FAIL"  # unsupported payment story
    backlog = json.loads(run.path("output/backlog.json").read_text("utf-8"))
    assert len(backlog["findings"]) == 2
    assert result["items"]["total"] == 3 and result["criteria"] == 2


def test_cli_audit_start(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ws = make_workspace(tmp_path)
    (ws / "b.csv").write_text("id,type,title,parent\n1,Epic,E,\n2,Initiative,X,1\n", encoding="utf-8")
    (ws / "map.json").write_text('{"Initiative": "feature"}', encoding="utf-8")
    base = [
        "start",
        "--workspace",
        str(ws),
        "--source",
        "prd.md",
        "--out",
        str(tmp_path / "o"),
        "--mode",
        "audit",
    ]
    assert main([*base, "--baseline", "b.csv"]) != 0
    capsys.readouterr()
    assert main([*base, "--baseline", "b.csv", "--type-map", str(ws / "map.json")]) == 0
    assert json.loads(capsys.readouterr().out)["run_id"]
