"""Single owner of controlled vocabularies shared by stage validators and the canonical schema.

Where the bundled JSON Schema already defines an enumeration, the runtime set is DERIVED from the
schema so the two can never drift (regression: dogfood c05, where the claims stage accepted a shape
the design-stage schema then rejected). Stage-only vocabularies (reader modality, reviewer verdicts)
live here once instead of being repeated per module.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from pbd.validation.schema import load_schema


def _enum(schema: str, *path: str) -> frozenset[str]:
    node: Any = load_schema(schema)
    for key in path:
        node = node[key]
    return frozenset(node["enum"])


@cache
def claim_categories() -> frozenset[str]:
    return _enum("backlog", "$defs", "claim", "properties", "category")


@cache
def uncertainty_levels() -> frozenset[str]:
    return _enum("defs", "$defs", "uncertainty", "properties", "level")


@cache
def claim_dispositions() -> frozenset[str]:
    return _enum("backlog", "$defs", "claim", "properties", "disposition", "properties", "status")


@cache
def finding_classifications() -> frozenset[str]:
    return _enum("backlog", "$defs", "finding", "properties", "classification")


@cache
def finding_severities() -> frozenset[str]:
    return _enum("backlog", "$defs", "finding", "properties", "severity")


# Reader-only vocabulary (what a source states; readers never infer or propose).
READER_MODALITIES = frozenset({"must", "should", "may", "must_not", "informative"})
READER_UNCERTAINTY = frozenset({"confirmed", "ambiguous", "conflicting", "unknown"})
MEMBER_STATUS = frozenset({"read", "partial", "unreadable", "skipped"})
INDEPENDENCE = frozenset({"separate_agent", "sequential_role"})

# Reviewer vocabulary.
VERDICTS = frozenset({"pass", "concern", "fail"})
SOURCE_SUPPORT = frozenset({"supported", "proposal_justified", "unsupported"})
INVEST_DIMENSIONS = ("independent", "negotiable", "valuable", "estimable", "small", "testable")
INVEST_RATINGS = frozenset({"supported", "concern", "unknown", "not_applicable"})
TASK_SUFFICIENCY = frozenset({"sufficient", "insufficient", "not_applicable"})
DUPLICATE_ASSESSMENTS = frozenset({"duplicate", "distinct", "overlap"})
REVIEW_FINDING_STATUS = frozenset({"candidate", "confirmed"})
# Reviewer obligation dispositions: the canonical claim dispositions minus UNASSESSED, plus BLOCKED.


def review_dispositions() -> frozenset[str]:
    return (claim_dispositions() - {"UNASSESSED"}) | {"BLOCKED"}


def design_dispositions() -> frozenset[str]:
    """What a designer may assign; SUPERSEDED is set only by approved decisions, UNASSESSED never."""
    return claim_dispositions() - {"UNASSESSED", "SUPERSEDED"}
