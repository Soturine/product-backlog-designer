"""Benchmark gold must stay consistent with its synthetic sources."""

from __future__ import annotations

import json

from tools.gold_check import check

from tests.conftest import REPO_ROOT


def test_every_gold_quote_resolves() -> None:
    import pytest

    pytest.importorskip(
        "pypdf", reason="PDF gold quotes resolve against the optional 'pdf' extra (text layer)"
    )
    assert check() == []


def test_gold_cases_cover_the_mandatory_scenarios() -> None:
    cases = sorted(p.stem for p in (REPO_ROOT / "benchmarks" / "gold").glob("*.json"))
    assert len([c for c in cases if c.startswith("c")]) == 12  # M1 cases; holdouts are h*/a*
    for name in cases:
        gold = json.loads((REPO_ROOT / "benchmarks" / "gold" / f"{name}.json").read_text(encoding="utf-8"))
        assert gold["synthetic"] is True
        if gold.get("mode") == "compare":
            assert gold["planted"] and gold["correct_controls"] and gold["no_winner"] is True
            for base in gold["baselines"]:
                assert (REPO_ROOT / "benchmarks" / "cases" / gold["case_dir"] / base).is_file()
            assert (REPO_ROOT / "benchmarks" / "cases" / gold["case_dir"] / "sources").is_dir()
            continue
        if gold.get("mode") == "audit":
            assert gold["planted_defects"] and gold["correct_items"]
            assert (REPO_ROOT / "benchmarks" / "cases" / name / gold["baseline"]).is_file()
        else:
            assert gold["obligations"] and gold["traps"]
        assert (REPO_ROOT / "benchmarks" / "cases" / name / "sources").is_dir()
