"""Stage vocabularies must stay consistent with the canonical schema (regression: dogfood c05)."""

from __future__ import annotations

from pbd import vocab
from pbd.pipeline import design, reading, review


def test_stage_sets_are_derived_from_schema() -> None:
    assert reading.CATEGORIES == design.CLAIM_CATEGORIES == vocab.claim_categories()
    assert vocab.uncertainty_levels() == design.UNCERTAINTY_LEVELS
    assert vocab.uncertainty_levels() >= reading.UNCERTAINTY
    assert vocab.finding_classifications() == review.CLASSIFICATIONS
    assert vocab.finding_severities() == review.SEVERITIES


def test_disposition_subsets() -> None:
    assert "UNASSESSED" not in vocab.design_dispositions() and "SUPERSEDED" not in vocab.design_dispositions()
    assert "BLOCKED" in vocab.review_dispositions() and "UNASSESSED" not in vocab.review_dispositions()
    assert vocab.design_dispositions() < vocab.claim_dispositions()
