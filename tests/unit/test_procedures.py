"""Procedures must keep the rules introduced for dogfood findings (ledger QL-001..QL-005)."""

from __future__ import annotations

import pytest

from tests.conftest import REPO_ROOT


@pytest.mark.parametrize(
    ("procedure", "phrase"),
    [
        ("designer.md", "Ambiguity is not a choice you make"),
        ("designer.md", "Every effective obligation must be verifiable where it lives"),
        ("designer.md", "Superseded behavior is not work"),
        ("designer.md", "Values stated by sources are confirmed fields"),
        ("designer.md", "use its design key"),
        ("reviewer.md", "claims_only_in_containers"),
        ("reviewer.md", "unsupported_assumption"),
        ("reader.md", "every field value a source states"),
        ("reader.md", "Uncertainty: confirmed, ambiguous, conflicting, unknown"),
    ],
)
def test_procedure_rule_present(procedure: str, phrase: str) -> None:
    text = (REPO_ROOT / "procedures" / procedure).read_text(encoding="utf-8")
    assert phrase.casefold() in text.casefold(), (procedure, phrase)
