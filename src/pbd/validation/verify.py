"""Verify that gate evidence is real, current and belongs to this run.

``check_gate_report`` only checks that the *declared* evidence has the right shape. This module
re-derives the facts from disk: for every PASS gate, each cited ``deterministic_check`` or
``review`` evidence must

* name an artifact (``ref``) inside the run output directory (no absolute paths or escapes);
* carry a ``digest`` equal to the SHA-256 of that artifact as it exists now;
* be listed in the run manifest with the same digest;
* carry the same ``run_id`` as the report and the manifest;
* name a ``stage`` that is ``complete`` in the manifest (not pending/failed/invalidated).

Coverage denominators must cite an inventory artifact listed in the manifest with a matching
digest. Any mismatch marks the gate ``verification: failed`` and the gate can no longer PASS.
"""

from __future__ import annotations

import copy
from pathlib import Path, PurePosixPath
from typing import Any

from pbd.core.canonical import file_digest
from pbd.validation.gates import GATE_BY_ID
from pbd.validation.schema import Issue

BOUND_TYPES = {"deterministic_check", "review"}


def _safe_artifact(root: Path, ref: str) -> Path | None:
    pure = PurePosixPath(ref.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or ":" in ref or not ref.strip():
        return None
    path = (root / pure).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def _check_artifact(
    gid: str, root: Path, ref: str | None, digest: str | None, manifest_digests: dict[str, str]
) -> list[Issue]:
    if not ref or not digest:
        return [Issue(gid, "evidence must cite an artifact ref and digest", "evidence_unbound")]
    path = _safe_artifact(root, ref)
    if path is None:
        return [Issue(gid, f"evidence ref escapes the run directory: {ref}", "evidence_unbound")]
    if not path.is_file():
        return [Issue(gid, f"evidence artifact missing: {ref}", "evidence_missing")]
    actual = file_digest(path)
    issues = []
    if actual != digest:
        issues.append(Issue(gid, f"evidence artifact changed since it was cited: {ref}", "evidence_stale"))
    listed = manifest_digests.get(ref)
    if listed is None:
        issues.append(Issue(gid, f"evidence artifact not registered in manifest: {ref}", "evidence_unbound"))
    elif listed != actual:
        issues.append(Issue(gid, f"manifest digest disagrees with artifact: {ref}", "evidence_stale"))
    return issues


def verify_gate_report(
    report: dict[str, Any], manifest: dict[str, Any], root: Path
) -> tuple[dict[str, Any], list[Issue]]:
    """Return a copy of ``report`` with ``verification`` set per gate, plus all issues found."""
    out = copy.deepcopy(report)
    issues: list[Issue] = []
    run_id = manifest.get("run_id")
    if report.get("run_id") != run_id:
        issues.append(Issue("$", "gate report belongs to a different run than the manifest", "foreign_run"))
    manifest_digests = {a["path"]: a["digest"] for a in manifest.get("artifacts", [])}
    stages = {s["name"]: s for s in manifest.get("stages", [])}

    for result in out.get("gates", []):
        gid = str(result.get("id"))
        gate_issues: list[Issue] = []
        bound = [ev for ev in result.get("evidence", []) if ev.get("type") in BOUND_TYPES]
        for ev in bound:
            if ev.get("run_id") != run_id:
                gate_issues.append(Issue(gid, "evidence belongs to another run or is unbound", "foreign_run"))
            stage = stages.get(str(ev.get("stage")))
            if stage is None:
                gate_issues.append(
                    Issue(gid, f"evidence cites unknown stage {ev.get('stage')}", "stage_invalid")
                )
            elif stage.get("status") != "complete":
                gate_issues.append(
                    Issue(gid, f"evidence stage {stage['name']} is {stage.get('status')}", "stage_invalid")
                )
            gate_issues.extend(_check_artifact(gid, root, ev.get("ref"), ev.get("digest"), manifest_digests))
        den = result.get("denominator")
        spec = GATE_BY_ID.get(gid)
        if den and spec is not None and spec.coverage:
            gate_issues.extend(
                _check_artifact(
                    gid, root, den.get("inventory_ref"), den.get("inventory_digest"), manifest_digests
                )
            )
        if result.get("status") == "PASS":
            if gate_issues:
                result["verification"] = "failed"
            elif bound:
                result["verification"] = "verified"
            else:
                result["verification"] = "declared"
        elif gate_issues:
            result["verification"] = "failed"
        issues.extend(gate_issues)
    return out, issues
