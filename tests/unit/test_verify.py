"""Declared vs verified gate evidence: artifacts must exist, match hashes and belong to this run/stage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pbd.core.canonical import file_digest
from pbd.validation.verify import verify_gate_report

RUN = "PBD-RUN-000000000001"


def _setup(tmp_path: Path, stage_status: str = "complete") -> tuple[dict[str, Any], dict[str, Any]]:
    (tmp_path / "checks.json").write_text('{"issues": []}', encoding="utf-8")
    (tmp_path / "review.json").write_text('{"reviewer": "independent"}', encoding="utf-8")
    d_checks, d_review = file_digest(tmp_path / "checks.json"), file_digest(tmp_path / "review.json")
    manifest = {
        "run_id": RUN,
        "artifacts": [
            {"path": "checks.json", "digest": d_checks, "bytes": 1},
            {"path": "review.json", "digest": d_review, "bytes": 1},
        ],
        "stages": [
            {"name": "gates", "status": "complete", "depends_on": []},
            {"name": "independent_review", "status": stage_status, "depends_on": []},
        ],
    }
    det = {
        "type": "deterministic_check",
        "ref": "checks.json",
        "digest": d_checks,
        "run_id": RUN,
        "stage": "gates",
    }
    rev = {
        "type": "review",
        "ref": "review.json",
        "digest": d_review,
        "run_id": RUN,
        "stage": "independent_review",
    }
    den = {
        "examined": 2,
        "total": 2,
        "provenance": "independent_inventory",
        "inventory_ref": "review.json",
        "inventory_digest": d_review,
    }
    report = {
        "run_id": RUN,
        "gates": [
            {"id": "G03", "status": "PASS", "evidence": [det]},
            {"id": "G02", "status": "PASS", "evidence": [rev], "denominator": den},
            {"id": "G05", "status": "PASS", "evidence": []},
            {"id": "G09", "status": "NOT_RUN", "evidence": []},
        ],
    }
    return report, manifest


def _status(report: dict[str, Any], gid: str) -> str | None:
    return next(g for g in report["gates"] if g["id"] == gid).get("verification")


def test_bound_evidence_is_verified(tmp_path: Path) -> None:
    report, manifest = _setup(tmp_path)
    out, issues = verify_gate_report(report, manifest, tmp_path)
    assert issues == []
    assert _status(out, "G03") == "verified" and _status(out, "G02") == "verified"
    assert _status(out, "G05") == "declared"  # no bound evidence: only declared, never verified
    assert _status(out, "G09") is None
    assert "verification" not in report["gates"][0]  # input not mutated


def test_modified_artifact_is_stale(tmp_path: Path) -> None:
    report, manifest = _setup(tmp_path)
    (tmp_path / "checks.json").write_text('{"issues": ["edited"]}', encoding="utf-8")
    out, issues = verify_gate_report(report, manifest, tmp_path)
    assert _status(out, "G03") == "failed"
    assert "evidence_stale" in {i.code for i in issues}


def test_missing_artifact(tmp_path: Path) -> None:
    report, manifest = _setup(tmp_path)
    (tmp_path / "checks.json").unlink()
    out, issues = verify_gate_report(report, manifest, tmp_path)
    assert _status(out, "G03") == "failed" and "evidence_missing" in {i.code for i in issues}


def test_evidence_from_other_run(tmp_path: Path) -> None:
    report, manifest = _setup(tmp_path)
    report["gates"][0]["evidence"][0]["run_id"] = "PBD-RUN-000000000002"
    out, issues = verify_gate_report(report, manifest, tmp_path)
    assert _status(out, "G03") == "failed" and "foreign_run" in {i.code for i in issues}
    report2, manifest2 = _setup(tmp_path)
    report2["run_id"] = "PBD-RUN-000000000002"
    _, issues2 = verify_gate_report(report2, manifest2, tmp_path)
    assert "foreign_run" in {i.code for i in issues2}


@pytest.mark.parametrize("status", ["invalidated", "pending", "failed"])
def test_evidence_from_non_complete_stage(tmp_path: Path, status: str) -> None:
    report, manifest = _setup(tmp_path, stage_status=status)
    out, issues = verify_gate_report(report, manifest, tmp_path)
    assert _status(out, "G02") == "failed" and "stage_invalid" in {i.code for i in issues}


def test_unregistered_artifact_and_escape(tmp_path: Path) -> None:
    report, manifest = _setup(tmp_path)
    manifest["artifacts"] = manifest["artifacts"][1:]
    _, issues = verify_gate_report(report, manifest, tmp_path)
    assert "evidence_unbound" in {i.code for i in issues}
    report2, manifest2 = _setup(tmp_path)
    report2["gates"][0]["evidence"][0]["ref"] = "../outside.json"
    out2, issues2 = verify_gate_report(report2, manifest2, tmp_path)
    assert _status(out2, "G03") == "failed" and "evidence_unbound" in {i.code for i in issues2}


def test_denominator_inventory_must_match(tmp_path: Path) -> None:
    report, manifest = _setup(tmp_path)
    report["gates"][1]["denominator"]["inventory_digest"] = "sha256:" + "f" * 64
    out, issues = verify_gate_report(report, manifest, tmp_path)
    assert _status(out, "G02") == "failed" and "evidence_stale" in {i.code for i in issues}
