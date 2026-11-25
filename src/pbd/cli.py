"""``pbd`` command-line runtime (deterministic support for the agent-led skill).

The CLI never performs semantic work and never contacts a network service: every command
executes inside :func:`pbd.security.network.offline`. Natural language or ``/pbd`` in the
host agent remains the user-facing entrypoint; these commands are runtime utilities.

Exit codes: 0 success, 1 validation/gate failure, 2 usage error, 3 scope/safety refusal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pbd import SCHEMA_VERSION, __version__
from pbd.core.canonical import CanonicalError, load_json_file
from pbd.core.host import doctor
from pbd.core.identity import KINDS, mint
from pbd.persistence.state import RunState, StateError
from pbd.security.network import offline
from pbd.security.privacy import scan_paths
from pbd.sources.registry import AUTHORITIES, build_sources
from pbd.sources.scope import Scope, ScopeError
from pbd.validation.gates import check_gate_report
from pbd.validation.invariants import check_backlog
from pbd.validation.schema import SCHEMA_FILES, load_schema, schema_for_document, validate

EXIT_OK, EXIT_INVALID, EXIT_USAGE, EXIT_REFUSED = 0, 1, 2, 3
MODES = [
    "generate",
    "audit",
    "compare",
    "refine",
    "check",
    "clarify",
    "render",
    "plan",
    "adr",
    "diff",
    "profile",
    "azure_package",
    "azure_export",
    "azure_publish",
    "azure_verify",
    "benchmark",
]


def _emit(value: Any) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor()
    if args.json:
        _emit(report)
    else:
        print(f"pbd {report['pbd_version']} (schema {report['schema_version']})")
        print(f"python {report['python']} supported={report['python_supported']} on {report['platform']}")
        print(f"host: {report['host']}  network: {report['network_mode']}  live transport: no")
        for loc in report["skill_installations"]:
            print(f"skill [{loc['scope']}]: {'present' if loc['present'] else 'absent'}")
    return EXIT_OK if report["python_supported"] else EXIT_INVALID


def cmd_schema(args: argparse.Namespace) -> int:
    if args.action == "list":
        for name in SCHEMA_FILES:
            print(name)
        return EXIT_OK
    if not args.name or args.name not in SCHEMA_FILES:
        print(f"unknown schema; choose one of: {', '.join(SCHEMA_FILES)}", file=sys.stderr)
        return EXIT_USAGE
    _emit(load_schema(args.name))
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        document = load_json_file(Path(args.file))
    except (OSError, ValueError, CanonicalError) as exc:
        print(f"unreadable document: {exc}", file=sys.stderr)
        return EXIT_INVALID
    name = args.schema or schema_for_document(document)
    if name is None:
        print("cannot infer schema from 'kind'; pass --schema", file=sys.stderr)
        return EXIT_USAGE
    issues = validate(name, document)
    if not issues and name == "backlog":
        issues = check_backlog(document)
    if not issues and name == "gate-report":
        issues = check_gate_report(document)
    result = {
        "file": args.file,
        "schema": name,
        "valid": not issues,
        "issues": [str(i) for i in issues],
        "note": "structural validity does not prove semantic coverage or quality",
    }
    _emit(result)
    return EXIT_OK if not issues else EXIT_INVALID


def _parse_selection(raw: str) -> tuple[str, str]:
    selector, _, authority = raw.partition("=")
    authority = authority or "other"
    if authority not in AUTHORITIES:
        raise argparse.ArgumentTypeError(f"unknown authority {authority!r}; one of {sorted(AUTHORITIES)}")
    return selector, authority


def cmd_inventory(args: argparse.Namespace) -> int:
    try:
        scope = Scope(Path(args.workspace))
        records = build_sources(scope, args.source)
    except (ScopeError, FileNotFoundError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    _emit({"note": "inventory only; no source has been semantically read", "sources": records})
    return EXIT_OK


def cmd_id(args: argparse.Namespace) -> int:
    for _ in range(args.count):
        print(mint(args.kind))
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.state_dir)
    try:
        if args.action == "init":
            state = RunState.create(root, args.mode, synthetic=args.synthetic, host=doctor()["host"])
        else:
            state = RunState.load(root, args.run_id)
    except (StateError, OSError, ValueError, CanonicalError) as exc:
        print(f"state error: {exc}", file=sys.stderr)
        return EXIT_INVALID
    _emit(
        {
            "run_id": state.manifest["run_id"],
            "mode": state.manifest["mode"],
            "status": state.manifest["status"],
            "stages": state.manifest["stages"],
            "manifest": str(state.manifest_path),
        }
    )
    return EXIT_OK


def cmd_privacy(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    paths: list[Path] = []
    for raw in args.paths:
        p = (root / raw).resolve()
        if p.is_dir():
            paths.extend(
                x
                for x in sorted(p.rglob("*"))
                if x.is_file()
                and not set(x.relative_to(root).parts)
                & {".git", ".venv", ".pbd", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
            )
        elif p.is_file():
            paths.append(p)
    findings = scan_paths(paths, root)
    _emit({"scanned_files": len(paths), "findings": [str(f) for f in findings]})
    return EXIT_OK if not findings else EXIT_INVALID


def _out_root(args: argparse.Namespace) -> Path:
    return Path(args.out)


def cmd_start(args: argparse.Namespace) -> int:
    from pbd.pipeline.run import RunError, normalize_request, start

    try:
        type_map = load_json_file(Path(args.type_map)) if args.type_map else None
        request = normalize_request(
            mode=args.mode,
            levels=args.levels.split(",") if args.levels else None,
            language=args.language,
            profile=args.profile,
            formats=args.formats.split(",") if args.formats else None,
            title=args.title,
            acceptance_style=args.acceptance_style,
            synthetic=args.synthetic,
        )
        run = start(
            _out_root(args),
            Path(args.workspace),
            args.source,
            request,
            host=doctor()["host"],
            baselines=args.baseline,
            type_map=type_map,
        )
    except (RunError, ScopeError, ValueError, OSError, CanonicalError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    _emit({"run_id": run.run_id, "run_dir": str(run.dir), "work_order": str(run.path("work-order.json"))})
    return EXIT_OK


def cmd_submit(args: argparse.Namespace) -> int:
    from pbd.pipeline.compare import submit_comparison
    from pbd.pipeline.design import submit_claims, submit_design
    from pbd.pipeline.reading import submit_ledger
    from pbd.pipeline.review import submit_review
    from pbd.pipeline.run import RunError, current

    handlers = {
        "reading": submit_ledger,
        "claims": submit_claims,
        "design": submit_design,
        "review": submit_review,
        "comparison": submit_comparison,
    }
    try:
        run = current(_out_root(args), args.run_id)
        payload = load_json_file(Path(args.file))
        result = handlers[args.stage](run, payload)
    except RunError as exc:
        _emit({"accepted": False, "errors": exc.errors})
        return EXIT_INVALID
    except (OSError, ValueError, CanonicalError) as exc:
        _emit({"accepted": False, "errors": [f"unreadable payload: {exc}"]})
        return EXIT_INVALID
    _emit({"accepted": True, **result, "work_order": str(run.path("work-order.json"))})
    return EXIT_OK


def cmd_finalize(args: argparse.Namespace) -> int:
    from pbd.pipeline.compare import finalize_comparison
    from pbd.pipeline.finalize import finalize
    from pbd.pipeline.run import RunError, current

    try:
        run = current(_out_root(args), args.run_id)
        result = (finalize_comparison if run.request()["mode"] == "compare" else finalize)(run)
    except RunError as exc:
        _emit({"finalized": False, "errors": exc.errors})
        return EXIT_INVALID
    _emit({"finalized": True, **result})
    return EXIT_OK


def cmd_work_order(args: argparse.Namespace) -> int:
    from pbd.pipeline.run import RunError, current

    try:
        run = current(_out_root(args), args.run_id)
    except RunError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID
    _emit(run.write_work_order())
    return EXIT_OK


def cmd_skill(args: argparse.Namespace) -> int:
    from pbd.core.install import InstallError, install, target_dir

    try:
        target = (
            Path(args.target)
            if args.target
            else target_dir(args.scope, Path(args.project) if args.project else None)
        )
        copied = install(target, force=args.force)
    except InstallError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    _emit(
        {
            "installed": str(target),
            "copied": copied,
            "note": "restart the agent host session to discover the skill; pbd still needs Python",
        }
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pbd",
        description=(
            "Product Backlog Designer runtime utilities (pre-alpha). Deterministic contracts only; "
            "semantic work is done by the host agent via natural language or /pbd. "
            "All commands run offline; no tracker is ever contacted."
        ),
    )
    parser.add_argument("--version", action="version", version=f"pbd {__version__} (schema {SCHEMA_VERSION})")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("doctor", help="report environment, host and skill installation (offline)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("schema", help="list or print bundled canonical schemas")
    p.add_argument("action", choices=["list", "show"])
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("validate", help="validate a canonical document (schema + invariants + gate rules)")
    p.add_argument("file")
    p.add_argument("--schema", choices=[n for n in SCHEMA_FILES if n != "defs"])
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("inventory", help="inventory explicitly selected sources (no semantic reading)")
    p.add_argument("--workspace", default=".", help="authorized workspace root")
    p.add_argument(
        "--source",
        action="append",
        required=True,
        type=_parse_selection,
        metavar="SELECTOR[=AUTHORITY]",
        help="one logical source; repeat for more",
    )
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("id", help="mint opaque stable identifiers")
    p.add_argument("kind", choices=sorted(KINDS))
    p.add_argument("--count", type=int, default=1)
    p.set_defaults(func=cmd_id)

    p = sub.add_parser("run", help="create or show private run state (.pbd/)")
    p.add_argument("action", choices=["init", "status"])
    p.add_argument("--mode", choices=MODES, default="generate")
    p.add_argument("--state-dir", default=".pbd")
    p.add_argument("--run-id")
    p.add_argument("--synthetic", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser(
        "privacy-scan", help="scan files for secrets, personal e-mails and private tracker URLs"
    )
    p.add_argument("paths", nargs="+")
    p.add_argument("--root", default=".")
    p.set_defaults(func=cmd_privacy)

    p = sub.add_parser(
        "start", help="start an agent-led generation run (inventory, extraction, reader assignments)"
    )
    p.add_argument("--workspace", default=".", help="authorized workspace root")
    p.add_argument(
        "--source",
        action="append",
        required=True,
        type=_parse_selection,
        metavar="SELECTOR[=AUTHORITY]",
        help="one logical source per declared file/directory/archive",
    )
    p.add_argument("--out", default="pbd-output", help="artifact root (default pbd-output)")
    p.add_argument(
        "--levels", help="comma list: epics,features,stories,acceptance,tasks,dependencies (default all)"
    )
    p.add_argument("--language", default="pt-BR")
    p.add_argument(
        "--profile",
        default="generic",
        help="generic, azure-agile, azure-scrum, azure-basic, azure-cmmi or a custom profile JSON file",
    )
    p.add_argument("--formats", help="comma list: html,json,md,csv,xlsx,mermaid,azure (html,json always)")
    p.add_argument("--acceptance-style", default="list", choices=["list", "table", "gherkin"])
    p.add_argument("--title")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument(
        "--mode",
        default="generate",
        choices=["generate", "audit", "compare"],
        help="audit needs one --baseline, compare needs two",
    )
    p.add_argument(
        "--baseline",
        action="append",
        help="existing backlog file (.json pbd.backlog/pbd.import or .csv); repeat for compare",
    )
    p.add_argument("--type-map", help="audit: JSON object mapping native work-item types to PBD types")
    p.set_defaults(func=cmd_start)

    for name, func, helptext in (
        ("finalize", cmd_finalize, "checks, verified gates, projections, exports and report.html"),
        ("work-order", cmd_work_order, "print the current work order (what the agent must do next)"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--out", default="pbd-output")
        p.add_argument("--run-id")
        p.set_defaults(func=func)

    p = sub.add_parser("skill", help="install the skill folder for an agent host (project or user scope)")
    p.add_argument("action", choices=["install"])
    p.add_argument("--scope", choices=["project", "user"], default="project")
    p.add_argument("--project", help="project root for project scope (default: current directory)")
    p.add_argument("--target", help="explicit destination folder (overrides scope)")
    p.add_argument("--force", action="store_true", help="replace an existing installed skill folder")
    p.set_defaults(func=cmd_skill)

    p = sub.add_parser("submit", help="submit an agent stage payload (all-or-nothing validation)")
    p.add_argument("stage", choices=["reading", "claims", "design", "review", "comparison"])
    p.add_argument("--file", required=True)
    p.add_argument("--out", default="pbd-output")
    p.add_argument("--run-id")
    p.set_defaults(func=cmd_submit)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    with offline():
        result: int = args.func(args)
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
