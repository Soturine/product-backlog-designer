"""``pbd azure`` subcommands. Local files in, local files out; the only transport is the mock.

    pbd azure snapshot --file export.json [--org O --project P] --out dir
    pbd azure prepare  --backlog backlog.json --package azure-import.json --snapshot export.json
                       --target O/P [--published published-state.json] --out dir
    pbd azure approve  --plan dir/publication-plan.json --target O/P --by NAME --out dir
    pbd azure apply    --plan dir/publication-plan.approved.json --mock-state mock.json --out dir
    pbd azure verify   --plan ... --receipt dir/publication-receipt.json --package ...
                       --mock-state mock.json --out dir

There is no flag, environment variable or configuration that selects a live transport.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pbd.core.canonical import load_json_file
from pbd.integrations.authority import AuthorizationDenied, RemoteAuthority
from pbd.integrations.azure import publish
from pbd.integrations.azure.snapshot import SnapshotError, discover_profile, load_snapshot
from pbd.integrations.azure.transport import FakeAzure
from pbd.persistence.atomic import atomic_write_json
from pbd.persistence.state import utc_now


def add_parser(sub: Any, func: Any) -> None:
    p = sub.add_parser("azure", help="local Azure DevOps snapshot, plan, approval and MOCK publication")
    p.add_argument("action", choices=["snapshot", "prepare", "approve", "apply", "verify"])
    p.add_argument("--file", help="snapshot: local export file")
    p.add_argument("--org")
    p.add_argument("--project")
    p.add_argument("--backlog")
    p.add_argument("--package")
    p.add_argument("--snapshot")
    p.add_argument("--target", help="organization/project the plan is bound to")
    p.add_argument("--published", help="published-state.json of the last verified publication")
    p.add_argument("--plan")
    p.add_argument("--by", help="approve: who approves this exact plan")
    p.add_argument("--receipt")
    p.add_argument("--transport", choices=["mock"], default="mock", help="only the in-memory mock exists")
    p.add_argument("--mock-state", help="local JSON file holding the mock target")
    p.add_argument("--language", default="en", help="interface language of publication-report.html")
    p.add_argument("--out", required=True)
    p.set_defaults(func=func)


def _report(out: Path, plan: dict[str, Any], receipt: dict[str, Any] | None, language: str) -> None:
    from pbd import __version__
    from pbd.persistence.atomic import atomic_write_bytes
    from pbd.render.report_html import render_publication_report

    html = render_publication_report(publish.preview(plan), receipt, __version__, language)
    atomic_write_bytes(out / "publication-report.html", html.encode("utf-8"))


def _need(args: argparse.Namespace, *names: str) -> None:
    missing = [n for n in names if not getattr(args, n.replace("-", "_"))]
    if missing:
        raise publish.PublishError(f"azure {args.action} needs --{' --'.join(missing)}")


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.out)
    if args.action == "snapshot":
        _need(args, "file")
        target = {"organization": args.org, "project": args.project} if args.org and args.project else None
        snap = load_snapshot(Path(args.file), target)
        atomic_write_json(out / "azure-snapshot.normalized.json", snap)
        atomic_write_json(out / "azure-discovered-profile.json", discover_profile(snap))
        return {"items": len(snap["items"]), "target": snap["target"]["namespace"], "notes": snap["notes"]}
    if args.action == "prepare":
        _need(args, "backlog", "package", "snapshot", "target")
        published = load_json_file(Path(args.published)) if args.published else None
        plan = publish.prepare(
            load_json_file(Path(args.backlog)),
            load_json_file(Path(args.package)),
            load_snapshot(Path(args.snapshot)),
            args.target,
            published,
        )
        atomic_write_json(out / "publication-plan.json", plan)
        prev = publish.preview(plan)
        atomic_write_json(out / "publication-preview.json", prev)
        _report(out, plan, None, args.language)
        return {"plan_digest": plan["plan_digest"], "counts": prev["counts"], "approved": False}
    if args.action == "approve":
        _need(args, "plan", "target", "by")
        approved = publish.approve(load_json_file(Path(args.plan)), args.target, args.by, utc_now())
        atomic_write_json(out / "publication-plan.approved.json", approved)
        return {"approved_plan_digest": approved["approval"]["approved_plan_digest"], "target": args.target}
    _need(args, "plan", "mock_state")
    plan = load_json_file(Path(args.plan))
    fake = FakeAzure.load(Path(args.mock_state))
    if not Path(args.mock_state).exists():
        fake.namespace = plan["target"]["namespace"]
    if args.action == "apply":
        receipt = publish.apply(
            plan, fake, RemoteAuthority(opted_in=True, transport="mock"), out / "journal.jsonl"
        )
        fake.save(Path(args.mock_state))
        atomic_write_json(out / "publication-receipt.json", receipt)
        _report(out, plan, receipt, args.language)
        return {"results": [r["outcome"] for r in receipt["results"]], "transport": "mock"}
    _need(args, "receipt", "package")
    verified = publish.verify(plan, load_json_file(Path(args.receipt)), fake)
    atomic_write_json(out / "publication-receipt.verified.json", verified)
    state = publish.published_state(plan, verified, load_json_file(Path(args.package)), fake)
    atomic_write_json(out / "published-state.json", state)
    _report(out, plan, verified, args.language)
    return {"verification": verified["verification"], "transport": "mock"}


def errors_of(exc: Exception) -> list[str]:
    if isinstance(exc, publish.PublishError):
        return exc.errors
    if isinstance(exc, AuthorizationDenied | SnapshotError):
        return [str(exc)]
    return [f"{type(exc).__name__}: {exc}"]


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)
