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
            execution=args.execution,
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


def _type_map(args: argparse.Namespace) -> dict[str, str] | None:
    return load_json_file(Path(args.type_map)) if getattr(args, "type_map", None) else None


def cmd_check(args: argparse.Namespace) -> int:
    from pbd.pipeline.importer import ImportError_
    from pbd.pipeline.modes import check

    try:
        result = check(Path(args.backlog), _type_map(args))
    except (ImportError_, OSError, ValueError, CanonicalError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    _emit(result)
    return EXIT_INVALID if result["status"] == "fail" else EXIT_OK


def cmd_clarify(args: argparse.Namespace) -> int:
    from pbd.pipeline.importer import ImportError_
    from pbd.pipeline.modes import clarify, clarify_markdown, load_json_backlog

    try:
        doc = clarify(load_json_backlog(Path(args.backlog)))
    except (ImportError_, OSError, ValueError, CanonicalError, KeyError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    if args.format == "md":
        sys.stdout.write(clarify_markdown(doc))
    else:
        _emit(doc)
    return EXIT_OK


def cmd_profile(args: argparse.Namespace) -> int:
    from pbd.core.execution import execution_profile
    from pbd.pipeline.importer import ImportError_
    from pbd.pipeline.modes import infer_profile
    from pbd.profiles import ProfileError, builtin_profiles, load_profile

    try:
        if args.action == "show":
            _emit(load_profile(args.target) if args.target else {"builtin": sorted(builtin_profiles())})
        elif args.action == "execution":
            _emit(execution_profile(args.target))
        else:
            if not args.target:
                print("refused: profile infer needs a backlog file", file=sys.stderr)
                return EXIT_REFUSED
            _emit(infer_profile(Path(args.target), _type_map(args), args.id))
    except (ImportError_, ProfileError, OSError, ValueError, CanonicalError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    return EXIT_OK


def cmd_refine(args: argparse.Namespace) -> int:
    from pbd.persistence.atomic import atomic_write_bytes, atomic_write_json
    from pbd.pipeline import refine
    from pbd.pipeline.modes import load_json_backlog

    out = Path(args.out)
    try:
        backlog = load_json_backlog(Path(args.backlog))
        if args.action == "plan":
            if not args.file:
                print("refused: refine plan needs --file <proposal.json>", file=sys.stderr)
                return EXIT_REFUSED
            doc = refine.plan(backlog, load_json_file(Path(args.file)))
            atomic_write_json(out / "refinement-plan.json", doc)
            atomic_write_bytes(out / "refinement-diff.md", refine.diff_markdown(doc, backlog).encode("utf-8"))
            _emit(
                {
                    "planned": len(doc["changes"]),
                    "plan": str(out / "refinement-plan.json"),
                    "plan_digest": doc["plan_digest"],
                    "applied": False,
                }
            )
            return EXIT_OK
        if not (args.plan and args.approve and args.plan_digest):
            print("refused: refine apply needs --plan, --approve and --plan-digest", file=sys.stderr)
            return EXIT_REFUSED
        res = refine.apply(
            backlog, load_json_file(Path(args.plan)), args.approve.split(","), args.plan_digest
        )
        atomic_write_json(out / "backlog.refined.json", res["backlog"])
        atomic_write_json(out / "refinement-result.json", res["result"])
        _emit(res["result"])
        return EXIT_OK
    except refine.RefineError as exc:
        _emit({"accepted": False, "errors": exc.errors})
        return EXIT_INVALID
    except (OSError, ValueError, CanonicalError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED


def cmd_azure(args: argparse.Namespace) -> int:
    from pbd.integrations.azure import cli as azure_cli

    try:
        _emit(azure_cli.run(args))
    except (ValueError, PermissionError, OSError, CanonicalError, KeyError) as exc:
        _emit({"accepted": False, "errors": azure_cli.errors_of(exc)})
        return EXIT_REFUSED
    return EXIT_OK


def cmd_plan(args: argparse.Namespace) -> int:
    from pbd import __version__
    from pbd.persistence.atomic import atomic_write_bytes, atomic_write_json
    from pbd.pipeline.modes import load_json_backlog
    from pbd.pipeline.planning import PlanningError, is_stale, plan, plan_markdown
    from pbd.render.report_html import render_plan_report

    out = Path(args.out)
    try:
        backlog = load_json_backlog(Path(args.backlog))
        if args.action == "check":
            if not args.plan:
                print("refused: plan check needs --plan", file=sys.stderr)
                return EXIT_REFUSED
            stale = is_stale(load_json_file(Path(args.plan)), backlog)
            _emit({"stale": stale, "plan": args.plan})
            return EXIT_INVALID if stale else EXIT_OK
        doc = plan(backlog, load_json_file(Path(args.input)) if args.input else None)
    except PlanningError as exc:
        _emit({"accepted": False, "errors": exc.errors})
        return EXIT_INVALID
    except (OSError, ValueError, CanonicalError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    atomic_write_json(out / "sprint-plan.json", doc)
    atomic_write_bytes(out / "sprint-plan.md", plan_markdown(doc).encode("utf-8"))
    html = render_plan_report(doc, args.title, backlog["language"], __version__)
    atomic_write_bytes(out / "plan-report.html", html.encode("utf-8"))
    _emit(
        {
            "sprints": len(doc["sprints"] or []),
            "sequence": len(doc["sequence"]),
            "unplanned": len(doc["unplanned"]),
            "committed": False,
            "notes": doc["notes"],
            **(
                {
                    "team_plan": {
                        "sprints": len(doc["team_plan"]["sprints"]),
                        "g10": doc["team_plan"]["g10"],
                        "violations": len(doc["team_plan"]["violations"]),
                        "unassigned_tasks": len(doc["team_plan"]["unassigned_tasks"]),
                        "unallocated": len(doc["team_plan"]["unallocated"]),
                    }
                }
                if doc.get("team_plan")
                else {}
            ),
        }
    )
    return EXIT_OK


def cmd_evolve(args: argparse.Namespace) -> int:
    from pbd import __version__
    from pbd.persistence.atomic import atomic_write_bytes, atomic_write_json
    from pbd.pipeline import refine
    from pbd.pipeline.evolution import diff_sources, stale_artifacts, summarize
    from pbd.pipeline.modes import load_json_backlog
    from pbd.render.report_html import render_evolution_report

    out = Path(args.out)
    try:
        if args.action == "diff":
            if not (args.old and args.new and args.source):
                print("refused: evolve diff needs --old, --new and --source", file=sys.stderr)
                return EXIT_REFUSED
            doc = diff_sources(Path(args.old), Path(args.new), args.source)
            atomic_write_json(out / "source-diff.json", doc)
            _emit({"summary": doc["summary"], "diff_digest": doc["diff_digest"]})
            return EXIT_OK
        backlog = load_json_backlog(Path(args.backlog))
        backlog.pop("_digest", None)
        if args.action == "stale":
            report = stale_artifacts(Path(args.dir or "."), backlog)
            _emit(report)
            return EXIT_INVALID if report["stale"] else EXIT_OK
        if args.action == "plan":
            doc = refine.plan(backlog, load_json_file(Path(args.file)))
            summary = summarize(backlog, doc)
            diff = load_json_file(Path(args.diff)) if args.diff else None
            atomic_write_json(out / "evolution-plan.json", doc)
            atomic_write_json(out / "evolution-summary.json", summary)
            atomic_write_bytes(out / "evolution-diff.md", refine.diff_markdown(doc, backlog).encode("utf-8"))
            html = render_evolution_report(backlog, doc, summary, __version__, diff)
            atomic_write_bytes(out / "evolution-report.html", html.encode("utf-8"))
            _emit({"counts": summary["counts"], "plan_digest": doc["plan_digest"], "applied": False})
            return EXIT_OK
        res = refine.apply(
            backlog, load_json_file(Path(args.plan)), args.approve.split(","), args.plan_digest
        )
        atomic_write_json(out / "backlog.evolved.json", res["backlog"])
        atomic_write_json(out / "evolution-result.json", res["result"])
        _emit(res["result"])
        return EXIT_OK
    except refine.RefineError as exc:
        _emit({"accepted": False, "errors": exc.errors})
        return EXIT_INVALID
    except (OSError, ValueError, CanonicalError, AttributeError, TypeError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED


def cmd_handoff(args: argparse.Namespace) -> int:
    from pbd.persistence.atomic import atomic_write_json
    from pbd.pipeline.handoff import build_handoff
    from pbd.pipeline.modes import load_json_backlog

    try:
        backlog = load_json_backlog(Path(args.backlog))
        backlog.pop("_digest", None)
        keys = load_json_file(Path(args.keys)) if args.keys else backlog.pop("keys", None)
        doc = build_handoff(backlog, keys)
    except (OSError, ValueError, CanonicalError, KeyError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    atomic_write_json(Path(args.out) / "ftd-handoff.json", doc)
    _emit(
        {
            "handoff": str(Path(args.out) / "ftd-handoff.json"),
            "sources": len(doc["sources"]),
            "seeds": len(doc["ftd_request_draft"]["seeds"]),
            "open_questions": len(doc["open_questions"]),
        }
    )
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
    p.add_argument(
        "--execution",
        choices=["economical", "balanced", "rigorous"],
        help="agent spending profile recorded in the work order (default balanced)",
    )
    p.set_defaults(func=cmd_start)

    from pbd.integrations.azure.cli import add_parser as add_azure

    add_azure(sub, cmd_azure)

    p = sub.add_parser(
        "plan", help="dependency order and sprint proposal from confirmed fields and your inputs"
    )
    p.add_argument("action", nargs="?", choices=["make", "check"], default="make")
    p.add_argument("--backlog", required=True)
    p.add_argument("--input", help="planning input JSON (capacity, calendar, technique, scenarios)")
    p.add_argument("--plan", help="check: a sprint-plan.json to test for staleness")
    p.add_argument("--title")
    p.add_argument("--out", default="pbd-plan")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("evolve", help="source diff, evolution plan/apply (lineage, decisions) and staleness")
    p.add_argument("action", choices=["diff", "plan", "apply", "stale"])
    p.add_argument("--old", help="diff: directory with the previous source versions")
    p.add_argument("--new", help="diff: directory with the new source versions")
    p.add_argument("--source", action="append", help="diff: selector relative to both directories")
    p.add_argument("--backlog", help="plan/apply/stale: current canonical backlog.json")
    p.add_argument("--file", help="plan: evolution proposal JSON")
    p.add_argument("--diff", help="plan: source-diff.json to show in the report")
    p.add_argument("--plan", help="apply: evolution-plan.json")
    p.add_argument("--approve", help="apply: change keys or all (human-edit overwrites need their keys)")
    p.add_argument("--plan-digest", help="apply: digest of the reviewed plan")
    p.add_argument("--dir", help="stale: directory with plans, packages and approvals to check")
    p.add_argument("--out", default="pbd-evolution")
    p.set_defaults(func=cmd_evolve)

    p = sub.add_parser("handoff", help="versioned handoff to Functional Test Designer (no test cases)")
    p.add_argument("target", choices=["ftd"])
    p.add_argument("--backlog", required=True)
    p.add_argument("--keys", help="optional id->key map (traceability.json keys) to show design keys")
    p.add_argument("--out", default="pbd-handoff")
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("check", help="structural health of a backlog file (no sources: structure only)")
    p.add_argument("backlog")
    p.add_argument("--type-map")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("clarify", help="questions and decisions a canonical backlog is waiting for")
    p.add_argument("backlog", help="PBD backlog.json")
    p.add_argument("--format", choices=["json", "md"], default="json")
    p.set_defaults(func=cmd_clarify)

    p = sub.add_parser("profile", help="show a process profile or infer a draft one from a backlog file")
    p.add_argument("action", choices=["show", "infer", "execution"])
    p.add_argument("target", nargs="?", help="profile id (show/execution) or backlog file (infer)")
    p.add_argument("--type-map")
    p.add_argument("--id", default="inferred", help="infer: id for the draft profile")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("refine", help="plan or apply a selective local refinement of a canonical backlog")
    p.add_argument("action", choices=["plan", "apply"])
    p.add_argument("--backlog", required=True, help="base PBD backlog.json")
    p.add_argument("--file", help="plan: refinement proposal JSON")
    p.add_argument("--plan", help="apply: refinement-plan.json produced by plan")
    p.add_argument("--approve", help="apply: comma list of change keys, or all")
    p.add_argument("--plan-digest", help="apply: digest of the reviewed plan")
    p.add_argument("--out", required=True, help="directory for the plan/diff or the refined backlog")
    p.set_defaults(func=cmd_refine)

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
