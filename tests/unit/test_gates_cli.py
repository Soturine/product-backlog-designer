from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pbd.cli import main
from pbd.core.host import detect_host, doctor
from pbd.validation.gates import GATES, check_gate_report, evaluate_result, not_run_report
from pbd.validation.schema import validate
from tests.conftest import FIXTURES, REPO_ROOT


# ---------- gates -----------------------------------------------------------------
def test_gate_ids_match_documented_table_without_renumbering() -> None:
    doc = (REPO_ROOT / "docs" / "quality-gates.md").read_text(encoding="utf-8")
    documented = dict(re.findall(r"^\| (G\d\d) ([^|]+?) \|", doc, flags=re.MULTILINE))
    assert [g.id for g in GATES] == [f"G{i:02d}" for i in range(1, 19)]
    for gate in GATES:
        assert gate.id in documented, gate.id
        assert documented[gate.id].strip().lower() == gate.name.lower(), gate.id


def test_documented_gate_kinds_match_registry() -> None:
    doc = (REPO_ROOT / "docs" / "quality-gates.md").read_text(encoding="utf-8")
    kinds = dict(re.findall(r"^\| (G\d\d) [^|]+\|[^|]+\| ([a-z/]+) \|", doc, flags=re.MULTILINE))
    for gate in GATES:
        documented = kinds[gate.id]
        # "deterministic/mixed": deterministic evidence is mandatory, review applies where relevant.
        expected = "deterministic" if documented == "deterministic/mixed" else documented
        assert gate.kind == expected, gate.id


def test_not_run_report_is_truthful_and_valid() -> None:
    report = not_run_report("PBD-RUN-000000000001", "no evidence collected", "0.1.0.dev0")
    assert validate("gate-report", report) == []
    assert check_gate_report(report) == []
    assert {g["status"] for g in report["gates"]} == {"NOT_RUN"}


@pytest.mark.parametrize("status", ["FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"])
def test_non_pass_statuses_need_no_evidence(status: str) -> None:
    assert evaluate_result({"id": "G05", "status": status, "evidence": []}) == []


def test_mixed_gate_needs_both_evidence_kinds() -> None:
    base = {"id": "G04", "status": "PASS"}
    assert evaluate_result({**base, "evidence": [{"type": "deterministic_check", "ref": "x"}]})
    assert evaluate_result({**base, "evidence": [{"type": "review", "ref": "x"}]})
    assert (
        evaluate_result(
            {
                **base,
                "evidence": [{"type": "review", "ref": "x"}, {"type": "deterministic_check", "ref": "y"}],
            }
        )
        == []
    )


# ---------- host ------------------------------------------------------------------
def test_detect_host_from_markers_only() -> None:
    assert detect_host({"CLAUDECODE": "1"}) == "claude-code"
    assert detect_host({}) == "unknown"


def test_doctor_reports_offline_and_no_live_transport() -> None:
    report = doctor({})
    assert report["network_mode"] == "offline" and report["live_transport_available"] is False
    assert report["python_supported"] is True


# ---------- CLI -------------------------------------------------------------------
def test_cli_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in ["doctor", "schema", "validate", "inventory", "id", "run", "privacy-scan"]:
        assert command in out
    assert "offline" in out
    assert main([]) == 2


def test_cli_validate_valid_and_invalid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    valid = FIXTURES / "schemas" / "valid" / "backlog.json"
    assert main(["validate", str(valid)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    doc = json.loads(valid.read_text(encoding="utf-8"))
    doc["items"][4]["parent"] = None
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert main(["validate", str(bad)]) == 1
    assert "orphan" in capsys.readouterr().out
    dup = tmp_path / "dup.json"
    dup.write_text('{"kind": "pbd.backlog", "kind": "x"}', encoding="utf-8")
    assert main(["validate", str(dup)]) == 1
    unknown = tmp_path / "unknown.json"
    unknown.write_text("{}", encoding="utf-8")
    assert main(["validate", str(unknown)]) == 2


def test_cli_inventory_refuses_escape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "prd.md").write_text("# PRD\n", encoding="utf-8")
    assert main(["inventory", "--workspace", str(tmp_path), "--source", "prd.md=functional"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sources"][0]["read_status"] == "not_read"
    assert main(["inventory", "--workspace", str(tmp_path), "--source", "../x.md"]) == 3


def test_cli_run_init_and_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state = tmp_path / ".pbd"
    assert main(["run", "init", "--state-dir", str(state), "--synthetic"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert main(["run", "status", "--state-dir", str(state)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["run_id"] == created["run_id"]
    assert status["status"]["remote_state"] == "not_contacted"
    assert main(["run", "status", "--state-dir", str(tmp_path / "none")]) == 1


def test_cli_schema_and_id(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema", "list"]) == 0
    assert "backlog" in capsys.readouterr().out
    assert main(["schema", "show", "backlog"]) == 0
    assert json.loads(capsys.readouterr().out)["$id"] == "urn:pbd:schema:v1:backlog"
    assert main(["schema", "show", "nope"]) == 2
    assert main(["id", "story", "--count", "3"]) == 0
    assert len(capsys.readouterr().out.split()) == 3
