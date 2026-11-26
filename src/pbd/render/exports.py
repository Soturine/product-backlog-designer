"""Deterministic projections and exports derived from ONE canonical backlog.

Every export carries ``backlog_digest`` so divergence between formats is detectable. No export
re-interprets semantics; they only reshape canonical data.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from graphlib import TopologicalSorter
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from pbd.core.canonical import digest, pretty_bytes
from pbd.profiles import has_acceptance_field, native_type
from pbd.render.richtext import criteria_html, criterion_sentence, labels, strip_html

# Link reference names as used by the Azure DevOps work item API. Mapping adapted from
# microsoft/azure-devops-mcp src/tools/work-items.ts (MIT, commit 2db70041); see ATTRIBUTION.md.
AZURE_LINK_TYPES = {
    "parent": "System.LinkTypes.Hierarchy-Reverse",
    "child": "System.LinkTypes.Hierarchy-Forward",
    "duplicate": "System.LinkTypes.Duplicate-Forward",
    "related": "System.LinkTypes.Related",
    "successor": "System.LinkTypes.Dependency-Forward",
    "predecessor": "System.LinkTypes.Dependency-Reverse",
}
TYPE_ORDER = {"epic": 0, "feature": 1, "story": 2, "enabler": 2, "spike": 2, "bug": 2, "task": 3}
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


# ---------------------------------------------------------------------------- helpers
def tree_order(backlog: dict[str, Any]) -> list[dict[str, Any]]:
    """Depth-first order (parents before children), stable by type then original order."""
    children: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    ids = {i["id"] for i in backlog["items"]}
    for item in backlog["items"]:
        parent = item["parent"] if item["parent"] in ids else None
        children[parent].append(item)
    out: list[dict[str, Any]] = []

    def walk(parent: str | None, depth: int) -> None:
        for item in children.get(parent, []):
            out.append({**item, "_depth": depth})
            walk(item["id"], depth + 1)

    walk(None, 0)
    return out


def criteria_by_parent(backlog: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for crit in sorted(backlog["criteria"], key=lambda c: (c["parent"], c.get("order", 0))):
        out[crit["parent"]].append(crit)
    return out


def safe_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(CSV_FORMULA_PREFIXES) else text


def _claim_index(backlog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in backlog["claims"]}


# ---------------------------------------------------------------------------- JSON projections
def projections(
    backlog: dict[str, Any], keys: dict[str, str], review: dict[str, Any] | None
) -> dict[str, Any]:
    bd = digest(backlog)
    claims = _claim_index(backlog)
    by_parent = criteria_by_parent(backlog)
    items = {i["id"]: i for i in backlog["items"]}
    forward: dict[str, list[str]] = defaultdict(list)
    for entry in backlog["items"] + backlog["criteria"]:
        for ref in entry.get("claim_refs", []):
            forward[ref].append(entry["id"])
    rev_items = {e["key"]: e for e in (review or {}).get("items", [])}
    rev_crits = {e["key"]: e for e in (review or {}).get("criteria", [])}
    requirements = {
        "kind": "pbd.requirements",
        "backlog_digest": bd,
        "sources": backlog["sources"],
        "claims": [
            {**c, "key": keys.get(c["id"]), "traced_by": sorted(forward.get(c["id"], []))}
            for c in backlog["claims"]
        ],
        "decisions": backlog["decisions"],
    }
    acceptance = {
        "kind": "pbd.acceptance-criteria",
        "backlog_digest": bd,
        "criteria": [
            {
                **c,
                "key": keys.get(c["id"]),
                "parent_title": items[c["parent"]]["title"],
                "statement": criterion_sentence(c),
                "review": rev_crits.get(keys.get(c["id"], "")),
            }
            for c in backlog["criteria"]
        ],
        "by_item": {pid: [c["id"] for c in crits] for pid, crits in sorted(by_parent.items())},
    }
    traceability = {
        "kind": "pbd.traceability",
        "backlog_digest": bd,
        "keys": dict(sorted(keys.items())),
        "forward": [
            {
                "claim": cid,
                "key": keys.get(cid),
                "status": c["disposition"]["status"],
                "covered_by": c["disposition"].get("covered_by", []),
                "traced_by": sorted(forward.get(cid, [])),
            }
            for cid, c in claims.items()
        ],
        "reverse": [
            {
                "id": e["id"],
                "key": keys.get(e["id"]),
                "claims": e.get("claim_refs", []),
                "locators": [
                    ev["locator"]
                    for ref in e.get("claim_refs", [])
                    for ev in claims[ref]["evidence"]
                    if "locator" in ev
                ],
                "technical_rationale": e.get("technical_rationale"),
                "review": (rev_items if "type" in e else rev_crits).get(keys.get(e["id"], "")),
            }
            for e in backlog["items"] + backlog["criteria"]
        ],
        "independent_obligations": (review or {}).get("independent_obligations", []),
    }
    return {
        "requirements.json": requirements,
        "acceptance-criteria.json": acceptance,
        "traceability.json": traceability,
        "findings.json": {"kind": "pbd.findings", "backlog_digest": bd, "findings": backlog["findings"]},
        "questions.json": {"kind": "pbd.questions", "backlog_digest": bd, "questions": backlog["questions"]},
    }


# ---------------------------------------------------------------------------- Markdown
def markdown(backlog: dict[str, Any], title: str) -> str:
    lab = labels(backlog["language"])
    by_parent = criteria_by_parent(backlog)
    claims = _claim_index(backlog)
    lines = [f"# {title}", "", f"Run `{backlog['run_id']}` · backlog digest `{digest(backlog)}`", ""]
    if backlog.get("synthetic"):
        lines += ["> Synthetic content.", ""]
    for item in tree_order(backlog):
        depth = min(item["_depth"] + 2, 6)
        lines.append(f"{'#' * depth} [{item['type']}] {item['title']} `{item['id']}`")
        if item.get("description"):
            lines += ["", strip_html(item["description"]["value"])]
        crits = by_parent.get(item["id"], [])
        if crits:
            lines += ["", f"**{lab['acceptance']}**", ""]
            lines += [f"- **{c['visible_id']}** {criterion_sentence(c)}" for c in crits]
        refs = [claims[r] for r in item.get("claim_refs", [])]
        if refs:
            lines += [
                "",
                "Trace: "
                + "; ".join(
                    f"{r['id']} ({ev['locator'].get('member', '')}:{ev['locator'].get('line_start', '')})"
                    for r in refs
                    for ev in r["evidence"][:1]
                    if "locator" in ev
                ),
            ]
        lines.append("")
    if backlog["questions"]:
        lines += (
            ["## Questions", ""] + [f"- {q['text']} — {q['impact']}" for q in backlog["questions"]] + [""]
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------- CSV / XLSX tables
def item_rows(backlog: dict[str, Any]) -> list[list[str]]:
    by_parent = criteria_by_parent(backlog)
    header = [
        "id",
        "type",
        "title",
        "parent",
        "depth",
        "description",
        "acceptance_criteria",
        "claims",
        "origin",
        "readiness",
        "readiness_review",
    ]
    rows = [header]
    from pbd.validation.invariants import disputed_items

    disputed = disputed_items(backlog)
    for item in tree_order(backlog):
        crits = by_parent.get(item["id"], [])
        rows.append(
            [
                item["id"],
                item["type"],
                item["title"],
                item["parent"] or "",
                str(item["_depth"]),
                strip_html(item.get("description", {}).get("value", "")),
                "\n".join(f"{c['visible_id']} {criterion_sentence(c)}" for c in crits),
                " ".join(item.get("claim_refs", [])),
                item["origin"],
                (item.get("readiness") or {}).get("status", "unassessed"),
                "disputed" if item["id"] in disputed else "",
            ]
        )
    return rows


def criteria_rows(backlog: dict[str, Any]) -> list[list[str]]:
    rows = [
        [
            "id",
            "visible_id",
            "parent",
            "style",
            "condition",
            "trigger",
            "expected_outcomes",
            "claims",
            "status",
        ]
    ]
    for c in sorted(backlog["criteria"], key=lambda c: (c["parent"], c.get("order", 0))):
        rows.append(
            [
                c["id"],
                c["visible_id"],
                c["parent"],
                c["style"],
                c.get("condition", c.get("text", "")),
                c.get("trigger", ""),
                "\n".join(c["expected_outcomes"]),
                " ".join(c["claim_refs"]),
                c["status"],
            ]
        )
    return rows


def trace_rows(backlog: dict[str, Any]) -> list[list[str]]:
    rows = [["claim", "status", "text", "source_member", "line_start", "covered_by"]]
    for c in backlog["claims"]:
        loc: dict[str, Any] = next((ev["locator"] for ev in c["evidence"] if "locator" in ev), {})
        rows.append(
            [
                c["id"],
                c["disposition"]["status"],
                c["text"],
                str(loc.get("member", "")),
                str(loc.get("line_start", "")),
                " ".join(c["disposition"].get("covered_by", [])),
            ]
        )
    return rows


def csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    for row in rows:
        writer.writerow([safe_cell(v) for v in row])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _col(n: int) -> str:
    name = ""
    while n:
        n, rem = divmod(n - 1, 26)
        name = chr(65 + rem) + name
    return name


def _sheet_xml(rows: list[list[str]]) -> str:
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    ]
    for r, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{_col(c)}{r}" t="inlineStr"><is><t xml:space="preserve">{xml_escape(str(v))}</t></is></c>'
            for c, v in enumerate(row, start=1)
        )
        out.append(f'<row r="{r}">{cells}</row>')
    out.append("</sheetData></worksheet>")
    return "".join(out)


def xlsx_bytes(sheets: list[tuple[str, list[list[str]]]]) -> bytes:
    """Minimal deterministic XLSX: inline strings only (no formulas can be created)."""
    buf = io.BytesIO()
    stamp = (2026, 1, 1, 0, 0, 0)
    ct = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    ]
    ct += [
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1)
    ]
    ct.append("</Types>")
    sheets_xml = "".join(
        f'<sheet name="{xml_escape(name[:31])}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _) in enumerate(sheets, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets_xml}</sheets></workbook>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            f'relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="xl/workbook.xml"/></Relationships>'
    )
    parts = [
        ("[Content_Types].xml", "".join(ct)),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", wb_rels),
    ]
    parts += [
        (f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows)) for i, (_, rows) in enumerate(sheets, start=1)
    ]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in parts:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


# ---------------------------------------------------------------------------- Mermaid
def mermaid(backlog: dict[str, Any]) -> str:
    lines = ["flowchart TD"]
    node = {i["id"]: f"n{n}" for n, i in enumerate(sorted(backlog["items"], key=lambda i: i["id"]))}
    for item in sorted(backlog["items"], key=lambda i: i["id"]):
        label = item["title"].replace('"', "'").replace("[", "(").replace("]", ")")
        lines.append(f'  {node[item["id"]]}["{item["type"]}: {label}"]')
    for item in backlog["items"]:
        if item["parent"] in node:
            lines.append(f"  {node[item['parent']]} --> {node[item['id']]}")
    for rel in backlog["relations"]:
        if rel["source"] in node and isinstance(rel["target"], str) and rel["target"] in node:
            lines.append(f"  {node[rel['source']]} -. {rel['type']} .-> {node[rel['target']]}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------- Azure local package
def azure_package(backlog: dict[str, Any], profile: dict[str, Any]) -> tuple[dict[str, Any], list[list[str]]]:
    """Local import package (never an authorization to publish). Relation URLs are placeholders
    ``pbd:<PBD-ID>`` resolved only by an approved publisher after target discovery (M3)."""
    fields = profile["fields"]
    lab = labels(backlog["language"])
    by_parent = criteria_by_parent(backlog)
    limitations = list(profile.get("limitations", []))
    work_items = []
    graph: dict[str, set[str]] = {
        i["id"]: ({i["parent"]} if i["parent"] else set()) for i in backlog["items"]
    }
    order = list(TopologicalSorter(graph).static_order())
    items = {i["id"]: i for i in backlog["items"]}
    for iid in order:
        item = items[iid]
        ntype = native_type(profile, item["type"])
        if ntype is None:
            limitations.append(f"{iid}: profile {profile['id']} has no native type for {item['type']}")
            continue
        description = item.get("description", {}).get("value", "")
        crits = by_parent.get(iid, [])
        values: dict[str, Any] = {fields["title"]: item["title"]}
        if crits:
            rendered = criteria_html(crits, item.get("acceptance_style", "list"), backlog["language"])
            if has_acceptance_field(profile, item["type"]):
                values[fields["acceptance"]] = rendered
            else:
                description += f"<p><strong>{lab['acceptance']}</strong></p>{rendered}"
                limitations.append(f"{iid}: acceptance criteria appended to description (no separate field)")
        values[fields["description"]] = description
        tag = profile.get("type_tags", {}).get(item["type"])
        if tag and fields.get("tags"):
            values[fields["tags"]] = tag
        proposals = {}
        for name, fv in (item.get("fields") or {}).items():
            ref = fields.get(
                profile.get("estimate_field", {}).get(item["type"], name) if name == "story_points" else name
            )
            if ref and fv.get("state") == "confirmed":
                values[ref] = fv["value"]
            elif ref and "value" in fv:
                proposals[ref] = {
                    "value": fv["value"],
                    "state": fv["state"],
                    "rationale": fv.get("rationale"),
                }
        patch = [{"op": "add", "path": f"/fields/{k}", "value": v} for k, v in values.items()]
        patch += [
            {"op": "add", "path": f"/multilineFieldsFormat/{k}", "value": "html"}
            for k in values
            if k in (fields.get("description"), fields.get("acceptance"))
        ]
        if item["parent"]:
            patch.append(
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {"rel": AZURE_LINK_TYPES["parent"], "url": f"pbd:{item['parent']}"},
                }
            )
        for rel in backlog["relations"]:
            if rel["type"] == "predecessor" and rel["target"] == iid and rel["status"] != "rejected":
                patch.append(
                    {
                        "op": "add",
                        "path": "/relations/-",
                        "value": {"rel": AZURE_LINK_TYPES["predecessor"], "url": f"pbd:{rel['source']}"},
                    }
                )
        work_items.append(
            {
                "pbd_id": iid,
                "work_item_type": ntype,
                "parent_pbd_id": item["parent"],
                "fields": values,
                "proposed_fields_not_written": proposals,
                "patch": patch,
            }
        )
    package = {
        "kind": "pbd.azure-import",
        "backlog_digest": digest(backlog),
        "profile": profile["id"],
        "profile_verified": bool(profile.get("verified")),
        "target": None,
        "note": (
            "Local package only. Not a publication and not an approval. Proposed fields are never written."
        ),
        "work_items": work_items,
        "limitations": sorted(set(limitations)),
    }
    csv_rows = [
        [
            "ID",
            "Work Item Type",
            "Title 1",
            "Title 2",
            "Title 3",
            "Title 4",
            "Description",
            "Acceptance Criteria",
        ]
    ]
    depth = {i["id"]: d["_depth"] for d in tree_order(backlog) for i in [d]}
    for wi in work_items:
        titles = ["", "", "", ""]
        titles[min(depth[wi["pbd_id"]], 3)] = wi["fields"][fields["title"]]
        csv_rows.append(
            [
                "",
                wi["work_item_type"],
                *titles,
                strip_html(wi["fields"][fields["description"]]),
                strip_html(wi["fields"].get(fields.get("acceptance") or "", "")),
            ]
        )
    return package, csv_rows


def json_bytes(value: Any) -> bytes:
    return pretty_bytes(value)
