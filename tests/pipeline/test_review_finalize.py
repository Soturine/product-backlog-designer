from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from pbd.cli import main
from pbd.core.canonical import file_digest
from pbd.pipeline.finalize import finalize
from pbd.pipeline.review import submit_review, validate_review
from pbd.pipeline.run import Run, RunError
from pbd.validation.schema import validate
from pbd.validation.verify import verify_gate_report
from tests.pipeline.helpers import designed_run, src_id

INVEST_OK = {
    d: {"rating": "supported", "note": "ok"}
    for d in ("independent", "negotiable", "valuable", "estimable", "small", "testable")
}


def review_payload(run: Run, independence: str = "separate_agent", agent: str = "reviewer") -> dict[str, Any]:
    p, d = src_id(run, "prd.md"), src_id(run, "decisoes")
    item = lambda k, **kw: {"key": k, "verdict": "pass", "source_support": "supported", **kw}  # noqa: E731
    return {
        "reviewer": {"agent": agent, "model": "test-model", "independence": independence},
        "sources_reread": [{"source_id": p, "complete": True}, {"source_id": d, "complete": True}],
        "independent_obligations": [
            {
                "key": "O1",
                "text": "reservar canteiro livre",
                "quote": "pode reservar um canteiro livre",
                "locator": {"source_id": p, "member": "prd.md", "line_start": 4},
                "disposition": "COVERED",
                "matched_claims": ["C1"],
                "covered_by": ["AC1"],
                "rationale": "AC1",
            },
            {
                "key": "O2",
                "text": "rejeitar reservado",
                "quote": "não aceita nova reserva",
                "locator": {"source_id": p, "member": "prd.md", "line_start": 5},
                "disposition": "COVERED",
                "matched_claims": ["C2"],
                "covered_by": ["AC2"],
                "rationale": "AC2",
            },
            {
                "key": "O3",
                "text": "listar reservas",
                "quote": "Minhas reservas",
                "locator": {"source_id": p, "member": "prd.md", "line_start": 6},
                "disposition": "COVERED",
                "matched_claims": ["C3"],
                "covered_by": ["AC4"],
                "rationale": "AC4",
            },
            {
                "key": "O4",
                "text": "aprovação manual (substituída)",
                "quote": "aprovadas manualmente",
                "locator": {"source_id": p, "member": "prd.md", "line_start": 7},
                "disposition": "SUPERSEDED",
                "matched_claims": ["C4"],
                "rationale": "ADR-001",
            },
            {
                "key": "O5",
                "text": "confirmação automática",
                "quote": "confirmadas automaticamente",
                "locator": {"source_id": d, "member": "adr-001.md", "line_start": 3},
                "disposition": "COVERED",
                "matched_claims": ["C5"],
                "covered_by": ["AC3"],
                "rationale": "AC3",
            },
        ],
        "items": [
            item("E1"),
            item("F1"),
            item("US1", invest={**INVEST_OK}, task_sufficiency="sufficient", readiness_check="agree"),
            item("US2", invest={**INVEST_OK}, task_sufficiency="sufficient", readiness_check="agree"),
            item("T1", readiness_check="agree"),
        ],
        "criteria": [item(k) for k in ("AC1", "AC2", "AC3", "AC4")],
        "duplicates": [],
        "dependencies_reviewed": True,
        "findings": [
            {
                "gate": "G06",
                "classification": "candidate_concern",
                "severity": "low",
                "expected": "Duração da temporada definida.",
                "actual": "Fonte não define duração.",
                "why": "Limite da reserva depende disso.",
                "impact": "Critério pode ficar incompleto.",
                "recommendation": "Responder Q1.",
                "affects": ["US1"],
            }
        ],
    }


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return designed_run(
        tmp_path,
        formats=["md", "csv", "xlsx", "mermaid", "azure"],
        profile="azure-agile",
        title="Horta — backlog",
    )


def test_review_requires_full_coverage_and_real_quotes(run: Run) -> None:
    payload = review_payload(run)
    payload["criteria"].pop()
    payload["independent_obligations"][0]["quote"] = "pode reservar dois canteiros"
    payload["sources_reread"].pop()
    errors = validate_review(run, payload)
    assert any("exactly once" in e for e in errors)
    assert any("quote not found" in e for e in errors)
    assert any("sources_reread" in e for e in errors)


def test_reviewer_cannot_claim_independence_when_it_designed(run: Run) -> None:
    errors = validate_review(run, review_payload(run, agent="designer"))
    assert any("same agent" in e for e in errors)
    story = review_payload(run)
    story["items"][2]["invest"].pop("small")
    assert any("invest.small" in e for e in validate_review(run, story))


def test_full_pipeline_finalizes_with_verified_gates(run: Run) -> None:
    submit_review(run, review_payload(run))
    result = finalize(run)
    out = run.path("output")
    for name in (
        "report.html",
        "backlog.json",
        "requirements.json",
        "acceptance-criteria.json",
        "traceability.json",
        "findings.json",
        "questions.json",
        "metrics.json",
        "gates.json",
        "manifest.json",
        "checks.json",
        "backlog.md",
        "backlog.csv",
        "backlog.xlsx",
        "dependencies.mmd",
        "azure/azure-import.json",
        "azure/azure-import.csv",
    ):
        assert (out / name).is_file(), name
    backlog = json.loads((out / "backlog.json").read_text(encoding="utf-8"))
    assert validate("backlog", backlog) == [] and len(backlog["findings"]) == 1
    gates = json.loads((out / "gates.json").read_text(encoding="utf-8"))
    assert validate("gate-report", gates) == []
    status = {g["id"]: g["status"] for g in gates["gates"]}
    assert status["G02"] == "PASS" and status["G13"] == "PASS" and status["G03"] == "PASS"
    assert status["G17"] == "BLOCKED"  # unverified default profile
    assert status["G18"] == "NOT_RUN" and status["G12"] == "NOT_APPLICABLE"
    assert all(g.get("verification") == "verified" for g in gates["gates"] if g["status"] == "PASS")
    _, issues = verify_gate_report(gates, run.state.manifest, run.dir)
    assert issues == []
    assert result["items"]["total"] == 5
    assert run.state.manifest["status"]["run"] == "complete"
    assert run.state.manifest["status"]["remote_state"] == "not_contacted"
    assert validate("run-manifest", run.state.manifest) == []


def test_exports_are_consistent_and_safe(run: Run) -> None:
    submit_review(run, review_payload(run))
    finalize(run)
    out = run.path("output")
    rows = list(csv.reader(io.StringIO((out / "backlog.csv").read_text(encoding="utf-8-sig"))))
    assert len(rows) - 1 == 5 and rows[1][1] == "epic"
    with zipfile.ZipFile(out / "backlog.xlsx") as zf:
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "<f>" not in sheet and "Reservar um canteiro livre" in sheet
    package = json.loads((out / "azure" / "azure-import.json").read_text(encoding="utf-8"))
    story = next(
        w
        for w in package["work_items"]
        if w["work_item_type"] == "User Story"
        and "US" not in w["pbd_id"]
        and w["fields"]["System.Title"] == "Reservar um canteiro livre"
    )
    assert story["fields"]["System.Description"].startswith("<p><strong>Eu como</strong>")
    assert "<strong>Dado</strong>" in story["fields"]["Microsoft.VSTS.Common.AcceptanceCriteria"]
    assert "Microsoft.VSTS.Scheduling.StoryPoints" in story["proposed_fields_not_written"]
    assert "Microsoft.VSTS.Scheduling.StoryPoints" not in story["fields"]
    assert any(
        op["value"]["rel"] == "System.LinkTypes.Hierarchy-Reverse"
        for op in story["patch"]
        if op["path"] == "/relations/-"
    )
    assert package["target"] is None and package["profile_verified"] is False
    html = (out / "report.html").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in html and "http://" not in html.split("<script>")[0].replace(
        "http://www.w3.org", ""
    )
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for art in manifest["artifacts"]:
        assert file_digest(run.path(art["path"])) == art["digest"], art["path"]


def test_sequential_review_blocks_g13(run: Run) -> None:
    submit_review(run, review_payload(run, independence="sequential_role", agent="designer"))
    finalize(run)
    gates = json.loads(run.path("output/gates.json").read_text(encoding="utf-8"))
    g13 = next(g for g in gates["gates"] if g["id"] == "G13")
    assert g13["status"] == "BLOCKED"
    assert run.state.manifest["status"]["semantic_review"] == "self_review_only"


def test_not_covered_obligation_fails_g02(run: Run) -> None:
    payload = review_payload(run)
    payload["independent_obligations"].append(
        {
            "key": "O6",
            "text": "pagamentos fora",
            "quote": "Pagamentos não fazem parte",
            "locator": {"source_id": src_id(run, "prd.md"), "member": "prd.md", "line_start": 10},
            "disposition": "NOT_COVERED",
            "rationale": "teste de mutação",
        }
    )
    submit_review(run, payload)
    finalize(run)
    gates = json.loads(run.path("output/gates.json").read_text(encoding="utf-8"))
    g02 = next(g for g in gates["gates"] if g["id"] == "G02")
    assert g02["status"] == "FAIL" and g02["denominator"]["breakdown"]["not_covered"] == 1


def test_finalize_once_and_requires_review(run: Run) -> None:
    with pytest.raises(RunError, match="independent_review"):
        finalize(run)
    submit_review(run, review_payload(run))
    finalize(run)
    with pytest.raises(RunError, match="already finalized"):
        finalize(run)


def test_cli_drives_the_pipeline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = designed_run(tmp_path)
    review_file = tmp_path / "review.json"
    review_file.write_text(json.dumps(review_payload(run), ensure_ascii=False), encoding="utf-8")
    out = str(tmp_path / "out")
    assert main(["work-order", "--out", out]) == 0
    assert json.loads(capsys.readouterr().out)["next_stage"] == "independent_review"
    bad = tmp_path / "bad.json"
    bad.write_text('{"reviewer": {}}', encoding="utf-8")
    assert main(["submit", "review", "--file", str(bad), "--out", out]) == 1
    assert json.loads(capsys.readouterr().out)["accepted"] is False
    assert main(["submit", "review", "--file", str(review_file), "--out", out]) == 0
    capsys.readouterr()
    assert main(["finalize", "--out", out]) == 0
    assert json.loads(capsys.readouterr().out)["finalized"] is True


def _g13(run: Run) -> dict[str, Any]:
    gates = json.loads(run.path("output/gates.json").read_text(encoding="utf-8"))
    return next(g for g in gates["gates"] if g["id"] == "G13")


def test_reviewer_that_was_a_reader_is_rejected(run: Run) -> None:
    """Claiming separate_agent while having been a reader is rejected at submission (G13 also checks)."""
    with pytest.raises(RunError, match="same agent that read"):
        submit_review(run, review_payload(run, agent="reader-prd"))


def test_g13_fails_when_reviewer_skipped_a_source(run: Run) -> None:
    payload = review_payload(run)
    payload["independent_obligations"] = [o for o in payload["independent_obligations"] if o["key"] != "O5"]
    submit_review(run, payload)
    finalize(run)
    g13 = _g13(run)
    assert g13["status"] == "FAIL" and "no verified obligation from source decisoes" in g13["reason"]


def test_g13_pass_cites_deterministic_evidence(run: Run) -> None:
    submit_review(run, review_payload(run))
    finalize(run)
    g13 = _g13(run)
    assert g13["status"] == "PASS" and g13["verification"] == "verified"
    assert {e["type"] for e in g13["evidence"]} == {"deterministic_check", "review"}
