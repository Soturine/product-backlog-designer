"""Run state with stage checkpoints and downstream invalidation.

Each stage records the digest of its inputs and outputs. When a stage is re-completed
with a different output digest, or a source digest changes, every transitive dependent
stage is marked ``invalidated`` (with reason) and must be recomputed before reuse.
"""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pbd import SCHEMA_VERSION, __version__
from pbd.core.canonical import load_json_file
from pbd.core.identity import mint
from pbd.persistence.atomic import Journal, atomic_write_json

# Default generation pipeline. Stages are internal; users never chain them manually.
DEFAULT_STAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("inventory", ()),
    ("reading", ("inventory",)),
    ("claims", ("reading",)),
    ("design", ("claims",)),
    ("independent_review", ("design", "reading")),
    ("gates", ("independent_review", "design")),
    ("render", ("gates", "design")),
)


class StateError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_manifest(mode: str, *, synthetic: bool = False, host: str = "unknown") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "pbd.run-manifest",
        "run_id": mint("run"),
        "mode": mode,
        "created_at": utc_now(),
        "synthetic": synthetic,
        "tool": {
            "name": "pbd",
            "version": __version__,
            "schema_version": SCHEMA_VERSION,
            "python": sys.version.split()[0],
            "platform": platform.system(),
            "host": host,
        },
        "network": {"mode": "offline", "remote_calls": 0},
        "sources": [],
        "stages": [{"name": n, "status": "pending", "depends_on": list(d)} for n, d in DEFAULT_STAGES],
        "artifacts": [],
        "status": {
            "run": "in_progress",
            "source_coverage": "not_assessed",
            "semantic_review": "not_run",
            "publication_readiness": "not_applicable",
            "remote_state": "not_contacted",
        },
        "limitations": [],
    }


class RunState:
    """Manifest-backed state in a private directory (default ``.pbd/``)."""

    def __init__(self, root: Path, manifest: dict[str, Any]) -> None:
        self.root = Path(root)
        self.manifest = manifest
        self.journal = Journal(self.root / "runs" / manifest["run_id"] / "journal.jsonl")

    # ----- persistence -------------------------------------------------
    @property
    def manifest_path(self) -> Path:
        return self.root / "runs" / str(self.manifest["run_id"]) / "manifest.json"

    def save(self) -> str:
        from pbd.validation.schema import validate

        issues = validate("run-manifest", self.manifest)
        if issues:
            raise StateError("refusing to persist invalid manifest: " + "; ".join(map(str, issues)))
        result = atomic_write_json(self.manifest_path, self.manifest)
        atomic_write_json(self.root / "current-run.json", {"run_id": self.manifest["run_id"]})
        return result

    @classmethod
    def create(cls, root: Path, mode: str, **kwargs: Any) -> RunState:
        state = cls(root, new_manifest(mode, **kwargs))
        state.save()
        state.journal.append("run_created", {"mode": mode})
        return state

    @classmethod
    def load(cls, root: Path, run_id: str | None = None) -> RunState:
        root = Path(root)
        if run_id is None:
            pointer = root / "current-run.json"
            if not pointer.exists():
                raise StateError("no current run")
            run_id = str(load_json_file(pointer)["run_id"])
        manifest = load_json_file(root / "runs" / run_id / "manifest.json")
        state = cls(root, manifest)
        state.journal.verify()
        return state

    # ----- stages ------------------------------------------------------
    def stage(self, name: str) -> dict[str, Any]:
        for stage in self.manifest["stages"]:
            if stage["name"] == name:
                return dict(stage)
        raise StateError(f"unknown stage {name}")

    def _stage_ref(self, name: str) -> dict[str, Any]:
        for stage in self.manifest["stages"]:
            if stage["name"] == name:
                result: dict[str, Any] = stage
                return result
        raise StateError(f"unknown stage {name}")

    def dependents(self, name: str) -> list[str]:
        out: list[str] = []
        frontier = [name]
        while frontier:
            current = frontier.pop()
            for stage in self.manifest["stages"]:
                if current in stage["depends_on"] and stage["name"] not in out:
                    out.append(stage["name"])
                    frontier.append(stage["name"])
        return out

    def complete(self, name: str, input_digest: str, output_digest: str) -> list[str]:
        """Record stage completion. Returns names of stages invalidated as a consequence."""
        stage = self._stage_ref(name)
        for dep in stage["depends_on"]:
            if self._stage_ref(dep)["status"] != "complete":
                raise StateError(f"stage {name} depends on incomplete stage {dep}")
        changed = stage.get("output_digest") not in (None, output_digest)
        stage.update(
            status="complete", input_digest=input_digest, output_digest=output_digest, completed_at=utc_now()
        )
        stage.pop("invalidated_reason", None)
        invalidated = (
            self.invalidate_dependents(name, f"upstream stage {name} output changed") if changed else []
        )
        self.journal.append(
            "stage_complete",
            {"stage": name, "input": input_digest, "output": output_digest, "invalidated": invalidated},
        )
        self.save()
        return invalidated

    def invalidate_dependents(self, name: str, reason: str) -> list[str]:
        changed = []
        for dep_name in self.dependents(name):
            dep = self._stage_ref(dep_name)
            if dep["status"] in ("complete", "failed", "blocked"):
                dep["status"] = "invalidated"
                dep["invalidated_reason"] = reason
                changed.append(dep_name)
        return changed

    def is_reusable(self, name: str, input_digest: str) -> bool:
        stage = self._stage_ref(name)
        return stage["status"] == "complete" and stage.get("input_digest") == input_digest

    # ----- sources -----------------------------------------------------
    def register_source(self, entry: dict[str, Any]) -> list[str]:
        """Register or refresh a source. A changed digest invalidates inventory and everything downstream."""
        invalidated: list[str] = []
        reason: str | None = None
        for existing in self.manifest["sources"]:
            if existing["source_id"] == entry["source_id"]:
                if existing["digest"] != entry["digest"]:
                    reason = f"source {entry['source_id']} changed"
                existing.clear()
                existing.update(entry)
                break
        else:
            self.manifest["sources"].append(entry)
            reason = f"source {entry['source_id']} added to scope"
        if reason is not None:
            inv = self._stage_ref("inventory")
            if inv["status"] in ("complete", "failed", "blocked"):
                inv["status"] = "invalidated"
                inv["invalidated_reason"] = reason
                invalidated.append("inventory")
            invalidated += self.invalidate_dependents("inventory", reason)
        self.journal.append(
            "source_registered",
            {"source_id": entry["source_id"], "digest": entry["digest"], "invalidated": invalidated},
        )
        self.save()
        return invalidated
