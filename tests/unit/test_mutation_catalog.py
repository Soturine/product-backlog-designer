"""Keep the mutation catalogue in sync with the code: every mutant must still apply exactly once."""

from __future__ import annotations

import json

import pytest

from tests.conftest import REPO_ROOT

CATALOG = json.loads((REPO_ROOT / "tests" / "mutation" / "mutants.json").read_text(encoding="utf-8"))[
    "mutants"
]


def test_mutant_ids_unique() -> None:
    ids = [m["id"] for m in CATALOG]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("mutant", CATALOG, ids=[m["id"] for m in CATALOG])
def test_mutant_applies(mutant: dict[str, str]) -> None:
    text = (REPO_ROOT / mutant["file"]).read_text(encoding="utf-8")
    assert mutant["old"] in text, f"{mutant['id']} drifted from {mutant['file']}"
    assert mutant["old"] != mutant["new"]
