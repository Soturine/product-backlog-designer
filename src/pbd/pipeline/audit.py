"""Audit and compare modes: imported backlogs take the place of the design stage.

``pbd start --mode audit --baseline <file>`` imports one baseline deterministically (see
``importer``) and ``--mode compare --baseline A --baseline B`` imports two. Reading and claims run
as in generation. When the claims are accepted, each baseline is compiled into a draft backlog
without changing its content: items and criteria keep ``origin: imported``, their raw text and no
claim references (no trace is invented).

- audit: the independent reviewer audits the single baseline with the ordinary review contract.
- compare: the reviewer submits a comparison (see ``compare``) judging both baselines against the
  same sources, with many-to-many mappings. Neither backlog is treated as gold.
"""

from __future__ import annotations

from typing import Any

from pbd import SCHEMA_VERSION
from pbd.core.identity import derive
from pbd.pipeline.run import BASELINE_FILES, Run, RunError
from pbd.render.sanitize import sanitize_html
from pbd.validation.invariants import check_backlog
from pbd.validation.schema import validate

IMPORT_RATIONALE = "Imported from the baseline as written; correctness is assessed by the independent audit."
STYLE = {"gherkin": "gherkin", "table": "table"}
DRAFTS = {
    "baseline": "stages/backlog.draft.json",
    "left": "stages/compare/left.draft.json",
    "right": "stages/compare/right.draft.json",
}


def _fields(raw: dict[str, Any]) -> dict[str, Any]:
    from pbd.pipeline.design import ALLOWED_FIELDS

    out = {}
    for name, value in raw.items():
        if name in ALLOWED_FIELDS and value not in (None, ""):
            out[name] = {
                "state": "proposed",
                "value": value,
                "rationale": "imported baseline value",
                "review_status": "unreviewed",
            }
    return out


def baseline_backlog(run: Run, base: dict[str, Any]) -> dict[str, Any]:
    """Canonical draft backlog (with ``keys``) for one imported baseline."""
    from pbd.pipeline.design import _source_records, _strip_keys  # shared with generation

    claims_doc = run.read("stages/claims.json")
    language = run.request()["language"]
    anchor = {"baseline": base["digest"]}
    ids = {i["key"]: derive(i["type"], {**anchor, "native": i["native_id"]}) for i in base["items"]}
    items, criteria = [], []
    for it in base["items"]:
        item: dict[str, Any] = {
            "id": ids[it["key"]],
            "type": it["type"],
            "native_type": it["native_type"],
            "title": it["title"] or it["native_id"],
            "parent": ids.get(it["parent"]) if it["parent"] else None,
            "claim_refs": [],
            "origin": "imported",
            "status": "draft",
        }
        if not it["native_id"].startswith("PBD-"):
            ref = {"system": "baseline", "namespace": base["source_file"], "native_id": it["native_id"]}
            item["external_refs"] = [ref]
        if it["description_raw"].strip():
            value = sanitize_html(it["description_raw"])
            item["description"] = {"format": "html", "value": value, "language": language}
        if it["type"] in ("story", "enabler", "spike", "bug"):
            item["acceptance_style"] = STYLE.get(it["acceptance_style"], "list")
        fields = _fields(it["fields_raw"])
        if fields:
            item["fields"] = fields
        items.append(item)
    for n, crit in enumerate(base["criteria"]):
        cid = derive("criterion", {**anchor, "native": crit["key"]})
        ids[crit["key"]] = cid
        criteria.append(
            {
                "id": cid,
                "parent": ids[crit["parent"]],
                "visible_id": crit["key"].rsplit(".", 1)[-1],
                "order": n,
                "style": crit["style"],
                "text": crit["raw"],
                "expected_outcomes": [crit["raw"]],
                "claim_refs": [],
                "origin": "imported",
                "status": "proposed",
                "rationale": IMPORT_RATIONALE,
                "raw": crit["raw"],
            }
        )
    backlog: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "pbd.backlog",
        "run_id": run.run_id,
        "language": language,
        "synthetic": bool(run.request().get("synthetic")),
        "profile": run.request()["profile"],
        "sources": _source_records(run),
        "claims": _strip_keys(claims_doc["claims"], ("key", "reader_refs")),
        "items": items,
        "criteria": criteria,
        "relations": [],
        "questions": [],
        "decisions": _strip_keys(claims_doc["decisions"]),
        "findings": [],
    }
    issues = validate("backlog", backlog) or check_backlog(backlog)
    if issues:
        raise RunError(
            f"imported baseline {base['source_file']} does not form a valid backlog", [str(i) for i in issues]
        )
    backlog["keys"] = {
        **{v: k for k, v in ids.items()},
        **{c["id"]: c["key"] for c in claims_doc["claims"]},
        **{d["id"]: d["key"] for d in claims_doc["decisions"]},
    }
    return backlog


def _side(base: dict[str, Any]) -> dict[str, Any]:
    return {
        "baseline": {k: base[k] for k in ("source_file", "format", "digest")},
        "items": [{"key": i["key"], "type": i["type"], "native_id": i["native_id"]} for i in base["items"]],
        "criteria": [{"key": c["key"], "parent": c["parent"]} for c in base["criteria"]],
    }


def compile_baseline(run: Run) -> dict[str, Any]:
    """Compile the imported baseline(s) as the design stage (audit: one, compare: two)."""
    mode = run.request()["mode"]
    labels = ["baseline"] if mode == "audit" else ["left", "right"]
    sides = {}
    for label in labels:
        base = run.read(BASELINE_FILES[label])
        run.write_artifact(DRAFTS[label], baseline_backlog(run, base))
        sides[label] = _side(base)
    designer = {"agent": "baseline-import", "model": "none (deterministic import)"}
    if mode == "audit":
        design = {"designer": designer, "mode": "audit", **sides["baseline"]}
    else:
        design = {
            "designer": designer,
            "mode": "compare",
            "sides": sides,
            # flat views keep generic tooling (work order, key checks) working
            "items": sides["left"]["items"] + sides["right"]["items"],
            "criteria": sides["left"]["criteria"] + sides["right"]["criteria"],
        }
    run.write_artifact("stages/design.json", design)
    run.save()
    produced = DRAFTS["baseline"] if mode == "audit" else DRAFTS["left"]
    run.state.complete(
        "design", str(run.artifact_digest("stages/claims.json")), str(run.artifact_digest(produced))
    )
    summary: dict[str, Any] = {
        label: {"items": len(s["items"]), "criteria": len(s["criteria"]), **s["baseline"]}
        for label, s in sides.items()
    }
    if mode == "audit":
        summary["items"] = len(sides["baseline"]["items"])
    return summary
