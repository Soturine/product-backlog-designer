"""FTD handoff: originals with roles, no authority claimed, verified tracker links only."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from pbd.cli import main
from pbd.pipeline.finalize import finalize
from pbd.pipeline.handoff import FTD_ROLE, build_handoff
from pbd.pipeline.review import submit_review
from tests.pipeline.helpers import designed_run
from tests.pipeline.test_review_finalize import review_payload


@pytest.fixture(scope="module")
def backlog_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    run = designed_run(tmp_path_factory.mktemp("ftd"), title="Horta")
    submit_review(run, review_payload(run))
    finalize(run)
    return run.path("output/backlog.json")


def test_roles_requirements_questions_and_seeds(backlog_path: Path) -> None:
    b = json.loads(backlog_path.read_text(encoding="utf-8"))
    doc = build_handoff(b)
    assert doc["kind"] == "pbd.ftd-handoff" and doc["handoff_version"] == "1.1"
    roles = {s["selector"]: s["ftd_role"] for s in doc["sources"]}
    assert roles == {"prd.md": "FUNCTIONAL_AUTHORITY", "decisoes": "FUNCTIONAL_AUTHORITY"}
    assert all(m["digest"] for s in doc["sources"] for m in s["members"])
    assert any(r["evidence"] and r["evidence"][0]["quote"] for r in doc["requirements"])
    assert len(doc["ftd_request_draft"]["seeds"]) == len(b["criteria"])
    assert doc["ftd_request_draft"]["ambiguities"] == [
        q["text"] for q in b["questions"] if q["status"] == "open"
    ]
    assert (
        FTD_ROLE["technical"] == "TECHNICAL_CONTEXT"
        and FTD_ROLE["implementation_evidence"] == "IMPLEMENTATION_EVIDENCE"
    )


def test_tracker_links_only_when_verified(backlog_path: Path) -> None:
    b = copy.deepcopy(json.loads(backlog_path.read_text(encoding="utf-8")))
    b["items"][0]["external_refs"] = [
        {"system": "azure-devops", "namespace": "o/p", "native_id": "1", "verified": True},
        {"system": "azure-devops", "namespace": "o/p", "native_id": "2"},
    ]
    links = build_handoff(b)["work_items"][0]["tracker_links"]
    assert [x["native_id"] for x in links] == ["1"]


def test_handoff_cli(backlog_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["handoff", "ftd", "--backlog", str(backlog_path), "--out", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["seeds"] > 0 and (tmp_path / "ftd-handoff.json").exists()
