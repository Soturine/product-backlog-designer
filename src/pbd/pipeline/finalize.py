"""Finalize: canonical backlog → deterministic checks → verified gates → projections → report."""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from typing import Any

from pbd import __version__
from pbd.core.canonical import bytes_digest, digest, loads_strict
from pbd.core.identity import derive
from pbd.pipeline.gates_engine import compute_gates
from pbd.pipeline.run import Run, RunError, require_stage
from pbd.profiles import load_profile, native_type
from pbd.render import exports
from pbd.render.report_html import render_report
from pbd.security.privacy import scan_text
from pbd.validation.gates import check_gate_report
from pbd.validation.invariants import check_backlog
from pbd.validation.schema import validate
from pbd.validation.verify import verify_gate_report

HIERARCHY_CODES = {
    "duplicate_id",
    "orphan",
    "invalid_parent",
    "cycle_hierarchy",
    "duplicate_binding",
    "namespace_mix",
}
TRACE_CODES = {"trace_reciprocity", "trace_scope", "dangling_ref", "stale_locator"}


def _final_backlog(run: Run) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    draft = run.read("stages/backlog.draft.json")
    review = run.read("stages/review.json")
    keys: dict[str, str] = draft.pop("keys")
    by_key = {v: k for k, v in keys.items()}
    findings = []
    for f in review.get("findings") or []:
        anchor = digest(
            [f.get("gate"), f["classification"], sorted(f["affects"]), f["expected"], f["actual"]]
        )
        entry = {
            "id": derive("finding", {"run": run.run_id, "content": anchor}),
            "classification": f["classification"],
            "severity": f["severity"],
            "expected": f["expected"],
            "actual": f["actual"],
            "why": f["why"],
            "impact": f["impact"],
            "recommendation": f["recommendation"],
            "affects": sorted({by_key[a] for a in f["affects"] if a in by_key}),
            "evidence": [{"type": "review", "ref": "stages/review.json", "summary": "independent review"}],
            "review_status": f.get("review_status", "confirmed"),
        }
        if f.get("decision_needed"):
            entry["decision_needed"] = f["decision_needed"]
        if f.get("gate"):
            entry["gate"] = f["gate"]
        findings.append(entry)
    draft["findings"] = findings
    for item in draft["items"]:
        item["status"] = "reviewed"
    issues = validate("backlog", draft) or check_backlog(draft)
    if issues:
        raise RunError("final backlog failed validation", [str(i) for i in issues])
    return draft, keys, review


def _render_exports(
    backlog: dict[str, Any],
    keys: dict[str, str],
    review: dict[str, Any],
    request: dict[str, Any],
    profile: dict[str, Any],
    title: str,
) -> dict[str, bytes]:
    out: dict[str, bytes] = {"output/backlog.json": exports.json_bytes(backlog)}
    for name, value in exports.projections(backlog, keys, review).items():
        out[f"output/{name}"] = exports.json_bytes(value)
    formats = set(request["formats"])
    if "md" in formats:
        out["output/backlog.md"] = exports.markdown(backlog, title).encode("utf-8")
    if "csv" in formats:
        out["output/backlog.csv"] = exports.csv_bytes(exports.item_rows(backlog))
        out["output/acceptance-criteria.csv"] = exports.csv_bytes(exports.criteria_rows(backlog))
        out["output/traceability.csv"] = exports.csv_bytes(exports.trace_rows(backlog))
    if "xlsx" in formats:
        out["output/backlog.xlsx"] = exports.xlsx_bytes(
            [
                ("Items", exports.item_rows(backlog)),
                ("Criteria", exports.criteria_rows(backlog)),
                ("Traceability", exports.trace_rows(backlog)),
            ]
        )
    if "mermaid" in formats or "dependencies" in request["levels"]:
        out["output/dependencies.mmd"] = exports.mermaid(backlog).encode("utf-8")
    if "azure" in formats:
        package, rows = exports.azure_package(backlog, profile)
        out["output/azure/azure-import.json"] = exports.json_bytes(package)
        out["output/azure/azure-import.csv"] = exports.csv_bytes(rows)
    return out


def _checks(
    run: Run,
    backlog: dict[str, Any],
    rendered: dict[str, bytes],
    rerendered: dict[str, bytes],
    request: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    inv = run.inventory()
    total = read = partial = 0
    unread = []
    methods: Counter[str] = Counter()
    fallbacks = []
    for src in inv["sources"]:
        ledger = run.read(f"stages/reading/{src['id']}.json")
        for m in ledger["members"]:
            method = (m.get("reading") or {}).get("method")
            if m["status"] in ("read", "partial"):
                methods[method or "undeclared"] += 1
                if method == "extracted_text":
                    limits = "; ".join((m.get("reading") or {}).get("limitations") or [])
                    fallbacks.append(f"{src['selector']}/{m['path']}" + (f" ({limits})" if limits else ""))
            total += 1
            read += m["status"] == "read"
            partial += m["status"] == "partial"
            if m["status"] != "read":
                unread.append(f"{src['selector']}/{m['path']}: {m['status']} ({m.get('reason', '')})")
    issues = check_backlog(backlog)
    hierarchy = [
        str(i)
        for i in issues
        if i.code in HIERARCHY_CODES
        or (i.code == "cycle" and i.path == "$.items")
        or (i.code == "dangling_ref" and "parent" in i.message)
    ]
    trace = [str(i) for i in issues if i.code in TRACE_CODES]
    deps = [
        str(i)
        for i in issues
        if i.code in ("cycle", "self_loop", "duplicate_relation") and i.path != "$.items"
    ]
    change = [str(i) for i in issues if i.code in ("stale_scope", "supersession", "asymmetric_supersession")]
    crit_parents = {c["parent"] for c in backlog["criteria"]}
    no_criteria = (
        [
            i["id"]
            for i in backlog["items"]
            if i["type"] == "story"
            and (i.get("content") or {}).get("kind") in ("role_goal_benefit", "job_story")
            and i["id"] not in crit_parents
        ]
        if "acceptance" in request["levels"]
        else []
    )
    integrity = [f"non-deterministic export: {k}" for k in rendered if rendered[k] != rerendered.get(k)]
    n_items, n_crit = len(backlog["items"]), len(backlog["criteria"])
    if "output/backlog.csv" in rendered:
        rows = list(csv.reader(io.StringIO(rendered["output/backlog.csv"].decode("utf-8-sig"))))
        if len(rows) - 1 != n_items:
            integrity.append(f"backlog.csv has {len(rows) - 1} rows for {n_items} items")
    if "output/backlog.md" in rendered:
        headings = len(re.findall(r"^#{2,6} \[", rendered["output/backlog.md"].decode("utf-8"), flags=re.M))
        if headings != n_items:
            integrity.append(f"backlog.md has {headings} item headings for {n_items} items")
    acc = loads_strict(rendered["output/acceptance-criteria.json"])
    if len(acc["criteria"]) != n_crit:
        integrity.append("acceptance-criteria.json count differs from backlog")
    for name, data in rendered.items():
        if name.endswith(".json") and name != "output/backlog.json":
            doc = loads_strict(data)
            if isinstance(doc, dict) and doc.get("backlog_digest") not in (None, digest(backlog)):
                integrity.append(f"{name} derived from a different backlog")
    privacy = []
    for name, data in rendered.items():
        if not name.endswith(".xlsx"):
            privacy += [f"{name}:{f.line}:{f.rule}" for f in scan_text(data.decode("utf-8", "replace"), name)]
    net = run.state.manifest["network"]
    if net.get("mode") != "offline" or net.get("remote_calls", 0) != 0:
        privacy.append("run is not offline")
    compat = [
        f"{i['id']}: no native type for {i['type']} in {profile['id']}"
        for i in backlog["items"]
        if native_type(profile, i["type"]) is None
    ]
    g13 = _independence_evidence(run)
    signals = {"claims_only_in_containers": _container_only_claims(backlog, request)}
    return {
        "run_id": run.run_id,
        "validator_version": __version__,
        "G01": {
            "members_total": total,
            "members_read": read,
            "members_partial": partial,
            "reading_complete": total > 0 and read == total,
            "unread": unread,
            "reading_methods": dict(sorted(methods.items())),
            "fallback_members": fallbacks,
        },
        "G03": hierarchy,
        "G04": trace,
        "G06_stories_without_criteria": no_criteria,
        "G08": deps,
        "G11": integrity,
        "G15": change,
        "G13": g13,
        "signals": signals,
        "G16": privacy,
        "G17": compat,
        "artifact_digests": {k: bytes_digest(v) for k, v in sorted(rendered.items())},
    }


def _container_only_claims(backlog: dict[str, Any], request: dict[str, Any]) -> list[str]:
    """Effective claims represented only by epics/features (regression: dogfood c04, critical recall miss).

    A deterministic signal for the reviewer and the report, never a semantic verdict or gate outcome.
    """
    if "acceptance" not in request["levels"]:
        return []
    types = {i["id"]: i["type"] for i in backlog["items"]}
    out = []
    for claim in backlog["claims"]:
        disp = claim["disposition"]
        if claim["temporal"]["status"] != "effective" or disp["status"] not in (
            "COVERED",
            "PARTIALLY_COVERED",
        ):
            continue
        covering = [types.get(x, "criterion") for x in disp.get("covered_by", [])]
        if covering and all(t in ("epic", "feature") for t in covering):
            out.append(claim["id"])
    return out


def _independence_evidence(run: Run) -> list[str]:
    """Deterministic evidence for G13 beyond the reviewer's own declaration."""
    review = run.read("stages/review.json")
    reviewer = str(review["reviewer"].get("agent"))
    problems = []
    builders = {
        str(run.read("stages/design.json").get("designer", {}).get("agent")),
        str(run.read("stages/claims.json").get("orchestrator", {}).get("agent")),
    }
    for src in run.inventory()["sources"]:
        ledger = run.read(f"stages/reading/{src['id']}.json")
        builders.add(str(ledger["reader"].get("agent")))
        if ledger.get("obligations"):
            cited = [
                o
                for o in review.get("independent_obligations", [])
                if o.get("locator", {}).get("source_id") == src["id"]
            ]
            if not cited:
                problems.append(
                    f"reviewer inventory has no verified obligation from source {src['selector']}"
                )
    if reviewer in builders:
        problems.append(f"reviewer {reviewer} also acted as reader, orchestrator or designer")
    return problems


def _metrics(
    backlog: dict[str, Any], review: dict[str, Any], gates: dict[str, Any], checks: dict[str, Any]
) -> dict[str, Any]:
    by_type = Counter(i["type"] for i in backlog["items"])
    obligations = review.get("independent_obligations", [])
    ob = Counter(o["disposition"] for o in obligations)
    tasks_per_story = [
        sum(1 for t in backlog["items"] if t["parent"] == s["id"] and t["type"] == "task")
        for s in backlog["items"]
        if s["type"] == "story"
    ]
    return {
        "kind": "pbd.metrics",
        "backlog_digest": digest(backlog),
        "items": {"total": len(backlog["items"]), "by_type": dict(sorted(by_type.items()))},
        "criteria": {
            "total": len(backlog["criteria"]),
            "proposed": sum(1 for c in backlog["criteria"] if c["status"] == "proposed"),
            "by_style": dict(Counter(c["style"] for c in backlog["criteria"])),
        },
        "claims": {
            "total": len(backlog["claims"]),
            "by_disposition": dict(Counter(c["disposition"]["status"] for c in backlog["claims"])),
        },
        "coverage": {
            "covered": ob["COVERED"],
            "total": len(obligations),
            "provenance": "independent reviewer inventory",
            "breakdown": dict(sorted(ob.items())),
            "note": "denominator = obligations the independent reviewer extracted from the sources",
        },
        "sources": {
            "sources": len(backlog["sources"]),
            "members_total": checks["G01"]["members_total"],
            "members_read": checks["G01"]["members_read"],
        },
        "findings": {
            "total": len(backlog["findings"]),
            "by_severity": dict(Counter(f["severity"] for f in backlog["findings"])),
            "by_classification": dict(Counter(f["classification"] for f in backlog["findings"])),
        },
        "questions": {
            "open": sum(1 for q in backlog["questions"] if q["status"] == "open"),
            "blocking": sum(1 for q in backlog["questions"] if q["blocking"]),
        },
        "review": {
            "independence": review["reviewer"]["independence"],
            "model": review["reviewer"]["model"],
            "verdicts": dict(
                Counter(e["verdict"] for e in review.get("items", []) + review.get("criteria", []))
            ),
        },
        "tasks_per_story": {
            "min": min(tasks_per_story, default=0),
            "max": max(tasks_per_story, default=0),
            "stories": len(tasks_per_story),
        },
        "gates": dict(Counter(g["status"] for g in gates["gates"])),
    }


def finalize(run: Run) -> dict[str, Any]:
    if run.request()["mode"] == "compare":
        from pbd.pipeline.compare import finalize_comparison

        return finalize_comparison(run)
    require_stage(run, "independent_review")
    if run.stage_status("render") == "complete":
        raise RunError("run already finalized; use pbd render to re-render")
    request = run.request()
    profile = load_profile(request.get("profile_ref") or request["profile"])
    title = request.get("title") or "Product Backlog"
    backlog, keys, review = _final_backlog(run)
    rendered = _render_exports(backlog, keys, review, request, profile, title)
    rerendered = _render_exports(backlog, keys, review, request, profile, title)
    for rel, data in rendered.items():
        run.write_artifact(rel, data=data, media_type=_media(rel))
    checks = _checks(run, backlog, rendered, rerendered, request, profile)
    run.write_artifact("output/checks.json", checks)
    run.save()
    run.state.complete(
        "checks",
        digest([run.artifact_digest("stages/review.json"), run.artifact_digest("output/backlog.json")]),
        str(run.artifact_digest("output/checks.json")),
    )
    gates = compute_gates(run, {**backlog, "keys": keys}, review, checks)
    rule_issues = check_gate_report(gates)
    if rule_issues:
        raise RunError(
            "gate engine produced an inadmissible report (runtime defect)", [str(i) for i in rule_issues]
        )
    verified, issues = verify_gate_report(gates, run.state.manifest, run.dir)
    if issues:
        raise RunError("gate evidence verification failed", [str(i) for i in issues])
    run.write_artifact("output/gates.json", verified)
    run.save()
    run.state.complete(
        "gates", str(run.artifact_digest("output/checks.json")), str(run.artifact_digest("output/gates.json"))
    )
    metrics = _metrics(backlog, review, verified, checks)
    run.write_artifact("output/metrics.json", metrics)
    azure = (
        loads_strict(rendered["output/azure/azure-import.json"])
        if "output/azure/azure-import.json" in rendered
        else None
    )
    ctx = {
        "backlog": backlog,
        "keys": keys,
        "review": review,
        "gates": verified,
        "metrics": metrics,
        "title": title,
        "limitations": run.state.manifest["limitations"],
        "azure": azure,
        "version": __version__,
        "mode": request["mode"],
    }
    html_bytes = render_report(ctx).encode("utf-8")
    if html_bytes != render_report(ctx).encode("utf-8"):
        raise RunError("report rendering is not deterministic (runtime defect)")
    run.write_artifact("output/report.html", data=html_bytes, media_type="text/html")
    outputs = [a for a in run.state.manifest["artifacts"] if a["path"].startswith("output/")]
    run.write_artifact(
        "output/manifest.json",
        {
            "kind": "pbd.output-manifest",
            "run_id": run.run_id,
            "backlog_digest": digest(backlog),
            "artifacts": outputs,
            "status": run.state.manifest["status"],
        },
    )
    status = run.state.manifest["status"]
    status["run"] = "complete"
    status["publication_readiness"] = "local_package_ready" if azure else "not_applicable"
    status["remote_state"] = "not_contacted"
    run.state.manifest["gates_ref"] = "output/gates.json"
    run.save()
    run.state.complete(
        "render",
        str(run.artifact_digest("output/gates.json")),
        str(run.artifact_digest("output/report.html")),
    )
    run.write_work_order()
    return {
        "run_id": run.run_id,
        "report": str(run.path("output/report.html")),
        "gates": metrics["gates"],
        "items": metrics["items"],
        "criteria": metrics["criteria"]["total"],
    }


def _media(rel: str) -> str:
    return {
        ".json": "application/json",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".html": "text/html",
        ".mmd": "text/plain",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(rel[rel.rfind(".") :], "application/octet-stream")
