"""Deterministic import of an existing backlog for audit, comparison and refinement.

Supported inputs: a PBD canonical backlog (``kind: pbd.backlog``), the simple ``pbd.import`` JSON
format (``{"kind": "pbd.import", "items": [...]}``) and CSV with ``id,type,title,parent`` columns
plus optional ``description`` and ``acceptance_criteria``. Unsupported formats are refused.

Parsing is mechanical (types, hierarchy, list/table/Gherkin/line structure of acceptance text);
no meaning is inferred. Unknown work-item types fail closed unless an explicit type map is given.
Original values are preserved verbatim (``raw``) next to the normalized fields.
"""

from __future__ import annotations

import csv
import html
import io
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pbd.core.canonical import bytes_digest, loads_strict

TYPE_ALIASES = {
    "epic": "epic",
    "feature": "feature",
    "user story": "story",
    "story": "story",
    "historia": "story",
    "história de usuário": "story",
    "product backlog item": "story",
    "pbi": "story",
    "requirement": "story",
    "issue": "story",
    "enabler": "enabler",
    "spike": "spike",
    "bug": "bug",
    "task": "task",
    "tarefa": "task",
}
_KEY_SAFE = re.compile(r"[^A-Za-z0-9_.-]")
_GHERKIN_START = re.compile(
    r"^\s*(scenario|cenário|cenario|escenario|scenario outline|esquema do cenário)\b", re.IGNORECASE
)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


class ImportError_(ValueError):
    """Backlog import refused (format, structure or unmapped type)."""


class _Blocks(HTMLParser):
    """Collect list items, table rows and paragraphs from acceptance HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[str] = []
        self.rows: list[list[str]] = []
        self.header_rows = 0
        self.paragraphs: list[str] = []
        self._buf: list[str] = []
        self._cell: list[str] | None = None
        self._row: list[str] | None = None
        self._in_li = 0
        self._row_is_header = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self._in_li += 1
            self._buf = []
        elif tag == "tr":
            self._row, self._row_is_header = [], False
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._row_is_header = self._row_is_header or tag == "th"
        elif tag == "br":
            (self._cell if self._cell is not None else self._buf).append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._in_li:
            self._in_li -= 1
            text = " ".join("".join(self._buf).split())
            if text:
                self.items.append(text)
            self._buf = []
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                if self._row_is_header and not self.rows:
                    self.header_rows += 1
                else:
                    self.rows.append(self._row)
            self._row = None
        elif tag in ("p", "div") and not self._in_li and self._row is None:
            text = "".join(self._buf).strip()
            if text:
                self.paragraphs.extend(t.strip() for t in text.split("\n") if t.strip())
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        else:
            self._buf.append(data)

    def close(self) -> None:
        super().close()
        rest = "".join(self._buf).strip()
        if rest:
            self.paragraphs.extend(t.strip() for t in rest.split("\n") if t.strip())


def parse_acceptance(value: str) -> tuple[str, list[str], dict[str, int]]:
    """Split acceptance text into raw criterion strings. Returns (style, criteria, counts)."""
    if not value or not value.strip():
        return "none", [], {"raw_rows": 0, "criteria": 0}
    if "<" in value and ">" in value:
        parser = _Blocks()
        parser.feed(value)
        parser.close()
        if parser.rows:
            crits = [" | ".join(c for c in row if c) for row in parser.rows]
            return (
                "table",
                crits,
                {
                    "raw_rows": len(parser.rows) + parser.header_rows,
                    "header_rows": parser.header_rows,
                    "criteria": len(crits),
                },
            )
        if parser.items:
            return "list", parser.items, {"raw_rows": len(parser.items), "criteria": len(parser.items)}
        text = "\n".join(parser.paragraphs)
    else:
        text = html.unescape(value)
    lines = [ln.rstrip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
    if any(_GHERKIN_START.match(ln) for ln in lines):
        scenarios: list[list[str]] = []
        for ln in lines:
            if _GHERKIN_START.match(ln) or not scenarios:
                scenarios.append([ln.strip()])
            else:
                scenarios[-1].append(ln.strip())
        crits = [" / ".join(s) for s in scenarios]
        return "gherkin", crits, {"raw_rows": len(lines), "criteria": len(crits)}
    crits = [_BULLET.sub("", ln).strip() for ln in lines]
    return (
        "list" if any(_BULLET.match(ln) for ln in lines) else "prose",
        crits,
        {"raw_rows": len(lines), "criteria": len(crits)},
    )


def _canonical_type(native: str, type_map: dict[str, str]) -> str | None:
    key = native.strip().casefold()
    if key in type_map:
        return type_map[key]
    return TYPE_ALIASES.get(key)


def _key(prefix: str, native_id: str) -> str:
    safe = _KEY_SAFE.sub("_", str(native_id))[:36] or "x"
    return f"{prefix}{safe}" if not safe[0].isalpha() else safe


def _rows_from_csv(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {"id", "type", "title"}
    if not rows or not required <= {c.strip().casefold() for c in rows[0]}:
        raise ImportError_("CSV must contain id, type and title columns")
    out = []
    for row in rows:
        norm = {k.strip().casefold(): (v or "") for k, v in row.items() if k}
        fields = {
            k: v
            for k, v in norm.items()
            if k not in ("id", "type", "title", "parent", "description", "acceptance_criteria") and v != ""
        }
        out.append(
            {
                "id": norm["id"],
                "type": norm["type"],
                "title": norm["title"],
                "parent": norm.get("parent") or None,
                "description": norm.get("description", ""),
                "acceptance_criteria": norm.get("acceptance_criteria", ""),
                "fields": fields,
            }
        )
    return out


def _rows_from_pbd(doc: dict[str, Any]) -> list[dict[str, Any]]:
    crits: dict[str, list[str]] = {}
    for c in doc.get("criteria", []):
        crits.setdefault(c["parent"], []).append(c.get("text") or "; ".join(c.get("expected_outcomes", [])))
    return [
        {
            "id": i["id"],
            "type": i["type"],
            "title": i["title"],
            "parent": i.get("parent"),
            "description": i.get("description", {}).get("value", ""),
            "acceptance_criteria": "".join(f"<li>{html.escape(t)}</li>" for t in crits.get(i["id"], [])),
            "fields": {k: v.get("value") for k, v in (i.get("fields") or {}).items() if "value" in v},
        }
        for i in doc.get("items", [])
    ]


def load_backlog(
    path: Path, type_map: dict[str, str] | None = None, label: str = "baseline"
) -> dict[str, Any]:
    """Return a normalized import: items, criteria (raw), notes and the source digest."""
    path = Path(path)
    data = path.read_bytes()
    type_map = {k.casefold(): v for k, v in (type_map or {}).items()}
    if path.suffix.lower() == ".csv":
        rows, fmt = _rows_from_csv(data), "csv"
    elif path.suffix.lower() == ".json":
        doc = loads_strict(data)
        if isinstance(doc, dict) and doc.get("kind") == "pbd.backlog":
            rows, fmt = _rows_from_pbd(doc), "pbd.backlog"
        elif isinstance(doc, dict) and doc.get("kind") == "pbd.import" and isinstance(doc.get("items"), list):
            rows, fmt = doc["items"], "pbd.import"
        else:
            raise ImportError_("JSON backlog must be kind pbd.backlog or pbd.import")
    else:
        raise ImportError_(
            f"unsupported backlog format {path.suffix!r}; use .json (pbd.backlog/pbd.import) or .csv"
        )
    unknown = sorted(
        {str(r.get("type")) for r in rows if _canonical_type(str(r.get("type", "")), type_map) is None}
    )
    if unknown:
        raise ImportError_(
            f"unmapped work-item types {unknown}; pass an explicit type map (native type -> "
            "epic|feature|story|enabler|spike|bug|task)"
        )
    ids = [str(r.get("id", "")).strip() for r in rows]
    if any(not i for i in ids) or len(set(ids)) != len(ids):
        raise ImportError_("every imported item needs a unique, non-empty id")
    prefix = "L" if label == "left" else "R" if label == "right" else "I"
    keys = {i: _key(prefix, i) for i in ids}
    if len(set(keys.values())) != len(keys):
        raise ImportError_("imported ids collide after key normalization")
    items, criteria, notes = [], [], []
    for row in rows:
        native_id = str(row["id"]).strip()
        parent = str(row.get("parent")).strip() if row.get("parent") not in (None, "") else None
        if parent is not None and parent not in keys:
            notes.append(f"{native_id}: parent {parent} not in the imported set (kept as a root item)")
            parent = None
        style, crits, counts = parse_acceptance(str(row.get("acceptance_criteria") or ""))
        items.append(
            {
                "key": keys[native_id],
                "native_id": native_id,
                "native_type": str(row["type"]),
                "type": _canonical_type(str(row["type"]), type_map),
                "title": str(row.get("title", "")),
                "parent": keys[parent] if parent else None,
                "description_raw": str(row.get("description") or ""),
                "fields_raw": row.get("fields") or {},
                "acceptance_raw": str(row.get("acceptance_criteria") or ""),
                "acceptance_style": style,
                "acceptance_counts": counts,
            }
        )
        for n, text in enumerate(crits, start=1):
            criteria.append(
                {
                    "key": f"{keys[native_id]}.AC{n}",
                    "parent": keys[native_id],
                    "raw": text,
                    "style": "gherkin" if style == "gherkin" else "table" if style == "table" else "list",
                }
            )
    return {
        "kind": "pbd.imported-backlog",
        "label": label,
        "format": fmt,
        "source_file": path.name,
        "digest": bytes_digest(data),
        "items": items,
        "criteria": criteria,
        "notes": notes,
    }
