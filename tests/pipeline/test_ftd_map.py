"""PBD → FTD traceability sidecar (QL-021): exact ID tokens only, nothing inferred."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from pbd.cli import main
from pbd.pipeline.finalize import finalize
from pbd.pipeline.ftd_map import build_map, instructions_markdown
from pbd.pipeline.handoff import build_handoff
from pbd.pipeline.review import submit_review
from tests.pipeline.library_fixture import designed_run, review_payload

R7 = Path(__file__).resolve().parents[2] / "benchmarks" / "runs" / "corrective" / "r7"


@pytest.fixture(scope="module")
def backlog(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    run = designed_run(tmp_path_factory.mktemp("lib"), formats=["md"], title="Biblioteca")
    submit_review(run, review_payload(run))
    finalize(run)
    doc: dict[str, Any] = json.loads(run.path("output/backlog.json").read_text(encoding="utf-8"))
    return doc


def _ftd(handoff: dict[str, Any], dispositions: list[dict[str, Any]]) -> dict[str, Any]:
    """A synthetic FTD test-cases.json: FTD keeps each seed's text verbatim in its dispositions."""
    return {
        "schema_version": "2.2",
        "test_cases": [
            {"id": "TC-001", "status": "READY", "execution_status": "READY"},
            {"id": "TC-002", "status": "NEEDS_REVIEW", "execution_status": "NEEDS_REVIEW"},
            {
                "id": "TC-003",
                "status": "BLOCKED_EXTERNAL_DEPENDENCY",
                "execution_status": "BLOCKED_EXTERNAL_DEPENDENCY",
            },
        ],
        "guidance_dispositions": [
            {
                "item": "instructions.md#guidance-001",
                "text": "method",
                "disposition": "USED_FOR_ORDERING",
                "test_refs": [],
            },
            *dispositions,
        ],
    }


def _seed(handoff: dict[str, Any], n: int) -> str:
    return str(handoff["ftd_request_draft"]["seeds"][n]["text"])


def test_seeds_carry_canonical_ids_and_instructions_keep_them(backlog: dict[str, Any]) -> None:
    handoff = build_handoff(backlog)
    assert handoff["handoff_version"] == "1.1"
    crit_ids = {c["id"] for c in backlog["criteria"]}
    for seed in handoff["ftd_request_draft"]["seeds"]:
        assert seed["text"].startswith("[PBD-AC-") and seed["pbd_ids"][0] in crit_ids
    md = instructions_markdown(handoff)
    assert all(s["text"] in md for s in handoff["ftd_request_draft"]["seeds"])
    assert "Keep the `[PBD-…]` identifier" in md


def test_exact_many_to_many_links_blocked_and_designed_not_executed(backlog: dict[str, Any]) -> None:
    handoff = build_handoff(backlog)
    s0, s1 = _seed(handoff, 0), _seed(handoff, 1)
    ftd = _ftd(
        handoff,
        [
            {
                "item": "instructions.md#seed-001",
                "text": s0,
                "disposition": "MATERIALIZED",
                "test_refs": ["TC-001", "TC-002"],
            },
            {
                "item": "instructions.md#seed-002",
                "text": s1,
                "disposition": "ALREADY_COVERED",
                "test_refs": ["TC-002", "TC-003"],
            },
            {
                "item": "instructions.md#seed-003",
                "text": "[CA-01] paraphrased",
                "disposition": "QUESTION_REQUIRED",
                "test_refs": [],
            },
            {
                "item": "instructions.md#seed-004",
                "text": "[PBD-AC-0000000000ZZ] gone",
                "disposition": "MATERIALIZED",
                "test_refs": ["TC-009"],
            },
        ],
    )
    doc = build_map(handoff, ftd, backlog)
    by = {link["seed"]: link for link in doc["links"]}
    assert by["instructions.md#seed-001"]["status"] == "linked"
    assert by["instructions.md#seed-001"]["test_cases"] == ["TC-001", "TC-002"]
    assert by["instructions.md#seed-003"]["status"] == "unresolved"  # visible IDs repeat per story
    assert by["instructions.md#seed-004"]["status"] == "dangling"
    assert by["instructions.md#seed-004"]["missing_test_cases"] == ["TC-009"]
    c0 = handoff["ftd_request_draft"]["seeds"][1]["pbd_ids"][0]
    assert doc["by_pbd_id"][c0] == ["TC-002", "TC-003"]  # a test case can serve several criteria
    assert doc["counts"] == {
        "seeds": 4, "linked": 2, "unresolved": 1, "dangling": 1, "pbd_ids_linked": 2,
        "test_cases_total": 3, "test_cases_linked": 3, "test_cases_unlinked": 0,
        "designed": 3, "executed": 0, "blocked": 1,
    }  # fmt: skip
    assert doc["stale_against_backlog"] is False


def test_duplicate_anchors_stale_backlog_and_invalid_inputs(backlog: dict[str, Any]) -> None:
    handoff = build_handoff(backlog)
    s0 = _seed(handoff, 0)
    d = {
        "item": "instructions.md#seed-001",
        "text": s0,
        "disposition": "MATERIALIZED",
        "test_refs": ["TC-001"],
    }
    changed = copy.deepcopy(backlog)
    changed["items"][0]["title"] = "renamed"
    doc = build_map(handoff, _ftd(handoff, [d, dict(d)]), changed)
    assert doc["duplicate_seed_anchors"] == ["instructions.md#seed-001"]
    assert doc["stale_against_backlog"] is True
    with pytest.raises(ValueError, match="not a PBD FTD handoff"):
        build_map({"kind": "other"}, _ftd(handoff, []))
    with pytest.raises(ValueError, match=r"not an FTD test-cases.json"):
        build_map(handoff, {"test_cases": []})


def test_historical_r7_output_stays_unresolved_and_cli_writes_the_map(tmp_path: Path) -> None:
    """The real R7 run (handoff 1.0) only carried visible IDs: nothing may be linked from it."""
    out = tmp_path / "map"
    assert main(["handoff", "ftd-map", "--handoff", str(R7 / "ftd-handoff.json"),
                 "--ftd-test-cases", str(R7 / "test-cases.json"), "--out", str(out)]) == 0  # fmt: skip
    doc = json.loads((out / "ftd-map.json").read_text(encoding="utf-8"))
    assert doc["counts"]["linked"] == 0 and doc["counts"]["unresolved"] == doc["counts"]["seeds"] == 15
    assert doc["counts"]["designed"] == 48 and doc["counts"]["executed"] == 0
    assert main(["handoff", "ftd-map", "--out", str(out)]) != 0
