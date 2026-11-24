"""Benchmark gold must stay consistent with its synthetic sources."""

from __future__ import annotations

import json

from tools.gold_check import check

from tests.conftest import REPO_ROOT


def test_every_gold_quote_resolves() -> None:
    assert check() == []


def test_gold_cases_cover_the_mandatory_scenarios() -> None:
    cases = sorted(p.stem for p in (REPO_ROOT / "benchmarks" / "gold").glob("*.json"))
    assert len(cases) == 10
    for name in cases:
        gold = json.loads((REPO_ROOT / "benchmarks" / "gold" / f"{name}.json").read_text(encoding="utf-8"))
        assert gold["synthetic"] is True and gold["obligations"] and gold["traps"]
        assert (REPO_ROOT / "benchmarks" / "cases" / name / "sources").is_dir()
