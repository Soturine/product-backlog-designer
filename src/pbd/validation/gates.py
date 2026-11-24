"""Quality gate registry (G01-G13 unchanged, extensions G14-G18) and evidence rules.

A gate result can only be PASS when the evidence matches the gate kind:

* deterministic gates need at least one ``deterministic_check`` evidence entry;
* semantic gates need at least one ``review`` evidence entry (a real review record);
* mixed gates need both.

Coverage-style gates cannot pass on an empty or shrunken denominator, and a denominator
derived only from the generated set cannot certify coverage. Missing evidence is
reported as BLOCKED or NOT_RUN, never PASS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pbd.validation.schema import Issue


@dataclass(frozen=True)
class GateSpec:
    id: str
    name: str
    kind: str  # deterministic | semantic | mixed
    coverage: bool = False  # requires an independent denominator to PASS


GATES: tuple[GateSpec, ...] = (
    GateSpec("G01", "Source Integrity", "mixed", coverage=True),
    GateSpec("G02", "Requirements Coverage", "mixed", coverage=True),
    GateSpec("G03", "Hierarchy Integrity", "deterministic"),
    GateSpec("G04", "Traceability", "mixed"),
    GateSpec("G05", "Story Quality", "semantic"),
    GateSpec("G06", "Acceptance Quality", "semantic"),
    GateSpec("G07", "Task Coverage", "semantic"),
    GateSpec("G08", "Dependency Integrity", "mixed"),
    GateSpec("G09", "Scope Integrity", "semantic"),
    GateSpec("G10", "Planning Integrity", "mixed"),
    GateSpec("G11", "Artifact Integrity", "deterministic"),
    GateSpec("G12", "Publication Safety", "mixed"),
    GateSpec("G13", "Independent Review", "semantic", coverage=True),
    GateSpec("G14", "Semantic Duplication", "semantic"),
    GateSpec("G15", "Change Safety", "mixed"),
    GateSpec("G16", "Privacy and Offline Boundary", "mixed"),
    GateSpec("G17", "Target Compatibility", "mixed"),
    GateSpec("G18", "Round-trip Fidelity", "mixed"),
)
GATE_BY_ID = {g.id: g for g in GATES}
INDEPENDENT_PROVENANCE = {"independent_inventory", "benchmark_gold"}


def evaluate_result(result: dict[str, Any]) -> list[Issue]:
    """Return rule violations for a single gate result (empty list means admissible)."""
    gid = str(result.get("id"))
    spec = GATE_BY_ID.get(gid)
    if spec is None:
        return [Issue(gid, "unknown gate id", "gate")]
    if result.get("status") != "PASS":
        return []
    issues: list[Issue] = []
    types = {ev.get("type") for ev in result.get("evidence", [])}
    if spec.kind in ("deterministic", "mixed") and "deterministic_check" not in types:
        issues.append(
            Issue(gid, f"{spec.kind} gate PASS requires a recorded deterministic_check", "gate_evidence")
        )
    if spec.kind in ("semantic", "mixed") and "review" not in types:
        issues.append(Issue(gid, f"{spec.kind} gate PASS requires a recorded review", "gate_evidence"))
    if spec.coverage:
        den = result.get("denominator")
        if not den:
            issues.append(Issue(gid, "coverage gate PASS requires a denominator", "gate_denominator"))
        else:
            if den.get("total", 0) == 0:
                issues.append(
                    Issue(gid, "coverage gate cannot PASS with an empty denominator", "gate_denominator")
                )
            if den.get("examined", 0) < den.get("total", 0):
                issues.append(
                    Issue(gid, "coverage gate cannot PASS with incomplete examination", "gate_denominator")
                )
            if den.get("provenance") not in INDEPENDENT_PROVENANCE:
                issues.append(
                    Issue(
                        gid,
                        "coverage denominator must come from an independent inventory or gold",
                        "gate_denominator",
                    )
                )
    return issues


def check_gate_report(report: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[str] = set()
    for result in report.get("gates", []):
        gid = str(result.get("id"))
        if gid in seen:
            issues.append(Issue(gid, "gate reported more than once", "gate"))
        seen.add(gid)
        issues.extend(evaluate_result(result))
    return issues


def not_run_report(run_id: str, reason: str, validator_version: str) -> dict[str, Any]:
    """A truthful initial report: every gate NOT_RUN until real evidence exists."""
    from pbd import SCHEMA_VERSION

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "pbd.gate-report",
        "run_id": run_id,
        "gates": [
            {
                "id": g.id,
                "status": "NOT_RUN",
                "scope": g.name,
                "validator_version": validator_version,
                "reason": reason,
                "evidence": [],
            }
            for g in GATES
        ],
    }
