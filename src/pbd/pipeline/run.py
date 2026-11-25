"""Run directory, start, work orders and artifact registration.

Layout under the artifact root (default ``pbd-output/``)::

    current-run.json
    runs/<RUN>/manifest.json, journal.jsonl, request.json, work-order.json
    runs/<RUN>/sources/inventory.json, sources/text/<SRC>/<member>.txt
    runs/<RUN>/stages/reading/<SRC>.json, stages/claims.json, stages/design.json, stages/review.json
    runs/<RUN>/output/...   (finalize)
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from pbd.core.canonical import digest, file_digest, load_json_file
from pbd.core.execution import execution_profile
from pbd.persistence.atomic import atomic_write_bytes, atomic_write_json
from pbd.persistence.state import RunState, StateError
from pbd.pipeline import extract
from pbd.profiles import load_profile
from pbd.sources.registry import build_sources
from pbd.sources.scope import Scope

LEVELS = ("epics", "features", "stories", "acceptance", "tasks", "dependencies")
FORMATS = ("html", "json", "md", "csv", "xlsx", "mermaid", "azure")
DEFAULT_FORMATS = ("html", "json")
CHUNK_LINES = 300
BASELINES_PER_MODE = {"generate": 0, "audit": 1, "compare": 2}
BASELINE_FILES = {
    "baseline": "stages/baseline.json",
    "left": "stages/baseline-left.json",
    "right": "stages/baseline-right.json",
}
STAGE_FILES = {
    "claims": "stages/claims.json",
    "design": "stages/design.json",
    "independent_review": "stages/review.json",
}


class RunError(RuntimeError):
    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or [message]
        detail = "" if errors is None else "".join(f"\n  - {e}" for e in self.errors)
        super().__init__(message + detail)


class Run:
    def __init__(self, state: RunState) -> None:
        self.state = state
        self.dir = state.manifest_path.parent

    # ------------------------------------------------------------------ basics
    @property
    def run_id(self) -> str:
        return str(self.state.manifest["run_id"])

    def path(self, rel: str) -> Path:
        return self.dir / PurePosixPath(rel)

    def read(self, rel: str) -> Any:
        return load_json_file(self.path(rel))

    def request(self) -> dict[str, Any]:
        data: dict[str, Any] = self.read("request.json")
        return data

    def inventory(self) -> dict[str, Any]:
        data: dict[str, Any] = self.read("sources/inventory.json")
        return data

    def write_artifact(
        self, rel: str, value: Any = None, *, data: bytes | None = None, media_type: str = "application/json"
    ) -> str:
        """Write an artifact atomically and register path + digest in the manifest."""
        target = self.path(rel)
        if data is not None:
            atomic_write_bytes(target, data)
        else:
            atomic_write_json(target, value)
        real = file_digest(target)
        size = target.stat().st_size
        arts = [a for a in self.state.manifest["artifacts"] if a["path"] != rel]
        arts.append({"path": rel, "digest": real, "bytes": size, "media_type": media_type})
        self.state.manifest["artifacts"] = sorted(arts, key=lambda a: a["path"])
        return real

    def artifact_digest(self, rel: str) -> str | None:
        for art in self.state.manifest["artifacts"]:
            if art["path"] == rel:
                return str(art["digest"])
        return None

    def evidence(self, kind: str, rel: str, stage: str, summary: str) -> dict[str, Any]:
        """Typed evidence bound to an artifact of this run (for gates)."""
        ref_digest = self.artifact_digest(rel)
        if ref_digest is None:
            raise RunError(f"artifact {rel} is not registered")
        return {
            "type": kind,
            "ref": rel,
            "digest": ref_digest,
            "run_id": self.run_id,
            "stage": stage,
            "summary": summary,
        }

    def save(self) -> None:
        self.state.save()

    def stage_status(self, name: str) -> str:
        return str(self.state.stage(name)["status"])

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, root: Path, run_id: str | None = None) -> Run:
        return cls(RunState.load(Path(root), run_id))

    # ------------------------------------------------------------------ work order
    def write_work_order(self) -> dict[str, Any]:
        order = build_work_order(self)
        atomic_write_json(self.path("work-order.json"), order)
        return order


def normalize_request(
    *,
    mode: str = "generate",
    levels: list[str] | None = None,
    language: str = "pt-BR",
    profile: str = "generic",
    formats: list[str] | None = None,
    title: str | None = None,
    acceptance_style: str = "list",
    synthetic: bool = False,
    execution: str | None = None,
) -> dict[str, Any]:
    levels = list(levels or LEVELS)
    bad = sorted(set(levels) - set(LEVELS))
    if bad:
        raise RunError(f"unknown levels {bad}; choose from {list(LEVELS)}")
    formats = list(formats or DEFAULT_FORMATS)
    bad = sorted(set(formats) - set(FORMATS))
    if bad:
        raise RunError(f"unknown formats {bad}; choose from {list(FORMATS)}")
    for required in ("html", "json"):
        if required not in formats:
            formats.append(required)
    if acceptance_style not in ("list", "table", "gherkin"):
        raise RunError("acceptance style must be list, table or gherkin")
    prof = load_profile(profile)
    try:
        exec_profile = execution_profile(execution)
    except ValueError as exc:
        raise RunError(str(exc)) from exc
    return {
        "execution": exec_profile["id"],
        "mode": mode,
        "levels": [lv for lv in LEVELS if lv in levels],
        "omitted_levels": [lv for lv in LEVELS if lv not in levels],
        "language": language,
        "profile": prof["id"] if prof.get("id") else profile,
        "profile_ref": profile,
        "formats": formats,
        "title": title,
        "acceptance_style": acceptance_style,
        "synthetic": synthetic,
    }


def start(
    root: Path,
    workspace: Path,
    selections: list[tuple[str, str]],
    request: dict[str, Any],
    host: str = "unknown",
    baselines: list[str] | None = None,
    type_map: dict[str, str] | None = None,
) -> Run:
    """Create a run: inventory, extraction, reader assignments and the first work order.

    ``baselines`` are workspace-relative backlog files (one for audit, two for compare) imported
    before the run exists, so an unsupported or unmapped baseline refuses the run instead of
    leaving it half-built.
    """
    if not selections:
        raise RunError("at least one explicitly selected source is required")
    baselines = list(baselines or [])
    wanted = BASELINES_PER_MODE.get(request["mode"], 0)
    if len(baselines) != wanted:
        raise RunError(
            f"{request['mode']} mode takes {wanted} --baseline file(s); got {len(baselines)} "
            "(audit requires --baseline, compare requires two)"
        )
    scope = Scope(workspace)
    imported: dict[str, dict[str, Any]] = {}
    if baselines:
        from pbd.pipeline.importer import ImportError_, load_backlog

        labels = ["baseline"] if len(baselines) == 1 else ["left", "right"]
        for label, sel in zip(labels, baselines, strict=True):
            try:
                imported[label] = load_backlog(scope.resolve(sel), type_map, label=label)
            except ImportError_ as exc:
                raise RunError(f"baseline {sel} refused: {exc}") from exc
    records = build_sources(scope, selections)
    root = Path(root)
    state = RunState.create(root, request["mode"], synthetic=bool(request.get("synthetic")), host=host)
    run = Run(state)
    levels = request["levels"]
    state.manifest["selected_levels"] = [lv for lv in levels if lv != "dependencies"] + (
        ["dependencies"] if "dependencies" in levels else []
    )
    run.write_artifact("request.json", request)

    inventory: dict[str, Any] = {
        "run_id": run.run_id,
        "workspace_digest": digest(str(scope.workspace)),
        "sources": [],
    }
    for record in records:
        src_path = scope.resolve(record["selector"])
        members = []
        for member in record.get("members", []):
            entry: dict[str, Any] = {"path": member["path"], "inventory_status": member["status"]}
            if member["status"] != "pending":
                entry.update(readable=False, reason=member.get("reason", member["status"]))
                members.append(entry)
                continue
            try:
                raw = extract.read_member_bytes(src_path, record["kind"], member["path"])
                result = extract.extract(member["path"], raw)
            except (extract.ExtractionError, OSError, KeyError, ValueError) as exc:
                entry.update(readable=False, reason=str(exc) or type(exc).__name__)
                members.append(entry)
                continue
            # Native-first: the original is the primary reading input for every member; extracted
            # text is a verification layer and the fallback when the host cannot open the format.
            orig = f"sources/original/{record['id']}/{member['path']}"
            run.write_artifact(orig, data=raw, media_type="application/octet-stream")
            policy = extract.READING_POLICY[result.extractor]
            entry.update(
                original_ref=orig,
                format=result.extractor,
                native_reading=policy["native"],
                extracted_layer=policy["extracted_layer"],
            )
            if result.visual:
                entry.update(
                    readable=False,
                    visual=True,
                    extractor="image",
                    reason="visual content: requires agent vision (visual_transcription) or a transcription",
                    gaps=result.gaps,
                )
                members.append(entry)
                continue
            rel = f"sources/text/{record['id']}/{member['path']}.txt"
            line_count = len(result.text.splitlines())
            run.write_artifact(rel, data=result.text.encode("utf-8"), media_type="text/plain")
            entry.update(
                readable=True,
                text_ref=rel,
                lines=line_count,
                text_digest=file_digest(run.path(rel)),
                chunks=extract.chunks(line_count, CHUNK_LINES),
                extractor=result.extractor,
                encoding=result.encoding,
            )
            if result.gaps:
                entry["gaps"] = result.gaps
            if result.notes:
                entry["notes"] = result.notes
            if result.pages:
                entry["pages"] = result.pages
            if result.sheets:
                entry["sheets"] = result.sheets
            members.append(entry)
        record["members_text"] = members
        inventory["sources"].append(record)
        state.manifest["sources"].append(
            {
                "source_id": record["id"],
                "selector": record["selector"],
                "authority": record["authority"],
                "version": record["version"],
                "digest": record["digest"],
                "reader": {
                    "status": "not_started",
                    "independence": "not_recorded",
                    "members_total": len(members),
                    "members_read": 0,
                },
            }
        )
    inv_digest = run.write_artifact("sources/inventory.json", inventory)
    unreadable = [
        f"{s['selector']}: {m['path']} ({m['reason']})"
        for s in inventory["sources"]
        for m in s["members_text"]
        if not m["readable"]
    ]
    gapped = [
        f"{s['selector']}: {m['path']} ({'; '.join(m['gaps'])})"
        for s in inventory["sources"]
        for m in s["members_text"]
        if m.get("readable") and m.get("gaps")
    ]
    state.manifest["limitations"] = [f"unreadable member: {u}" for u in unreadable] + [
        f"extraction gaps: {g}" for g in gapped
    ]
    state.manifest["status"]["source_coverage"] = (
        "incomplete_reading" if unreadable or gapped else "not_assessed"
    )
    for label, base in imported.items():
        run.write_artifact(BASELINE_FILES[label], base)
        state.manifest["limitations"] += [f"{label}: {n}" for n in base["notes"]]
    state.save()
    state.complete("inventory", digest([selections, request]), inv_digest)
    run.write_work_order()
    return run


# ---------------------------------------------------------------------- work order
def _assignments(run: Run) -> list[dict[str, Any]]:
    inv = run.inventory()
    out = []
    for src in inv["sources"]:
        submitted = run.path(f"stages/reading/{src['id']}.json").exists()
        out.append(
            {
                "source_id": src["id"],
                "selector": src["selector"],
                "authority": src["authority"],
                "source_digest": src["digest"],
                "status": "SUBMITTED" if submitted else "PENDING",
                "result_file": f"stages/reading/{src['id']}.json",
                "members": [
                    {
                        k: m[k]
                        for k in (
                            "path",
                            "readable",
                            "visual",
                            "format",
                            "native_reading",
                            "extracted_layer",
                            "text_ref",
                            "original_ref",
                            "lines",
                            "chunks",
                            "pages",
                            "sheets",
                            "gaps",
                            "notes",
                            "encoding",
                            "reason",
                        )
                        if k in m
                    }
                    for m in src["members_text"]
                ],
            }
        )
    return out


def build_work_order(run: Run) -> dict[str, Any]:
    stages = {s["name"]: s["status"] for s in run.state.manifest["stages"]}
    order: dict[str, Any] = {
        "run_id": run.run_id,
        "run_dir": run.dir.name,
        "stages": stages,
        "request": run.request(),
        "execution": execution_profile(run.request().get("execution")),
    }
    if stages["reading"] != "complete":
        order.update(
            next_stage="reading",
            procedure="procedures/reader.md",
            instruction=(
                "Assign one logical reader per source below. Native-first: each reader opens every "
                "member's ORIGINAL (original_ref) with the host's native tools (file reader, PDF/vision "
                "reader), uses the text_ref lines to cite and verify quotes, and falls back to the "
                "extracted text only when the host cannot open the format, declaring it in "
                "members[].reading. One ledger per source; submit with: "
                "pbd submit reading --file <ledger.json>"
            ),
            reader_assignments=_assignments(run),
        )
    elif stages["claims"] != "complete":
        order.update(
            next_stage="claims",
            procedure="procedures/orchestrator.md",
            instruction=(
                "Reconcile all reader obligations into atomic claims; account for every reader "
                "obligation exactly once; submit with: pbd submit claims --file <claims.json>"
            ),
            reader_obligation_keys=_reader_keys(run),
        )
    elif stages["design"] != "complete":
        order.update(
            next_stage="design",
            procedure="procedures/designer.md",
            instruction=(
                "Design the requested levels from the claims; submit with: "
                "pbd submit design --file <design.json>"
            ),
            claims_file="stages/claims.json",
            levels=run.request()["levels"],
        )
    elif stages["independent_review"] != "complete":
        order.update(
            next_stage="independent_review",
            procedure="procedures/reviewer.md",
            instruction=(
                "A reviewer that did not design the backlog re-reads the ORIGINAL sources first, "
                "builds its own obligation inventory, then reviews every item and criterion; "
                "submit with: pbd submit review --file <review.json>"
            ),
            review_targets=_review_targets(run),
        )
        if run.request()["mode"] == "compare":
            order.update(
                procedure="procedures/reviewer.md#compare-mode",
                instruction=(
                    "COMPARE: re-read the ORIGINAL sources first and build your own obligation inventory; "
                    "for every obligation record the disposition of the left AND the right baseline; review "
                    "every item and criterion of both; map them many-to-many (equivalent, split, merge, "
                    "overlap, divergent, conflicting) with rationale; neither backlog is gold. Submit with: "
                    "pbd submit comparison --file <comparison.json>"
                ),
                sides={s: v["baseline"] for s, v in run.read("stages/design.json")["sides"].items()},
            )
        elif run.request()["mode"] == "audit":
            order["instruction"] += (
                ". AUDIT: the backlog under review is the imported baseline (origin imported, no "
                "claim references); judge it against the sources, never against what you would have "
                "designed. Every gap, divergence or unsupported item is a finding with expected, "
                "actual, why, impact and recommendation"
            )
            order["baseline"] = run.read("stages/design.json").get("baseline")
    else:
        order.update(next_stage="finalize", instruction="Run: pbd finalize")
    return order


def _reader_keys(run: Run) -> list[dict[str, str]]:
    keys: list[dict[str, str]] = []
    for src in run.inventory()["sources"]:
        rel = f"stages/reading/{src['id']}.json"
        if run.path(rel).exists():
            ledger = run.read(rel)
            keys.extend(
                {"ref": f"{src['id']}:{o['key']}", "text": o["text"]} for o in ledger.get("obligations", [])
            )
    return keys


def _review_targets(run: Run) -> dict[str, Any]:
    if not run.path("stages/design.json").exists():
        return {}
    design = run.read("stages/design.json")
    return {
        "items": [i["key"] for i in design.get("items", [])],
        "criteria": [c["key"] for c in design.get("criteria", [])],
    }


def require_stage(run: Run, stage: str) -> None:
    status = run.stage_status(stage)
    if status != "complete":
        raise RunError(f"stage {stage} is {status}; complete it first")


def current(root: Path, run_id: str | None = None) -> Run:
    try:
        return Run.load(root, run_id)
    except (StateError, FileNotFoundError) as exc:
        raise RunError(f"no run found under {root}: {exc}") from exc
