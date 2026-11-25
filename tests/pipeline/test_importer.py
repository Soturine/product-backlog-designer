"""Backlog importer: formats, fail-closed types, hierarchy and acceptance parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbd.pipeline.importer import ImportError_, load_backlog, parse_acceptance


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_csv_import_preserves_raw_and_hierarchy(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "b.csv",
        "id,type,title,parent,acceptance_criteria,priority\n"
        "10,Epic,Billing,,,\n"
        '11,User Story,Pay invoice,10,"- pays by card\n- pays by pix",2\n',
    )
    out = load_backlog(p)
    assert out["format"] == "csv" and out["digest"].startswith("sha256:")
    story = out["items"][1]
    assert story["type"] == "story" and story["native_type"] == "User Story"
    assert story["parent"] == out["items"][0]["key"]
    assert story["fields_raw"] == {"priority": "2"}
    assert [c["raw"] for c in out["criteria"]] == ["pays by card", "pays by pix"]


def test_unknown_type_fails_closed_unless_mapped(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "b.json",
        json.dumps({"kind": "pbd.import", "items": [{"id": "A", "type": "Initiative", "title": "x"}]}),
    )
    with pytest.raises(ImportError_, match="unmapped"):
        load_backlog(p)
    assert load_backlog(p, type_map={"Initiative": "epic"})["items"][0]["type"] == "epic"


def test_duplicate_ids_and_unsupported_format_refused(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "b.json",
        json.dumps(
            {
                "kind": "pbd.import",
                "items": [
                    {"id": "A", "type": "task", "title": "x"},
                    {"id": "A", "type": "task", "title": "y"},
                ],
            }
        ),
    )
    with pytest.raises(ImportError_, match="unique"):
        load_backlog(p)
    with pytest.raises(ImportError_, match="unsupported"):
        load_backlog(_write(tmp_path, "b.xml", "<x/>"))
    with pytest.raises(ImportError_, match="kind"):
        load_backlog(_write(tmp_path, "c.json", "{}"))


def test_orphan_parent_noted_not_invented(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "b.json",
        json.dumps(
            {"kind": "pbd.import", "items": [{"id": "A", "type": "story", "title": "x", "parent": "Z"}]}
        ),
    )
    out = load_backlog(p)
    assert out["items"][0]["parent"] is None and "parent Z" in out["notes"][0]


def test_acceptance_styles() -> None:
    assert parse_acceptance("")[0] == "none"
    style, crits, counts = parse_acceptance(
        "<table><tr><th>Given</th><th>Then</th></tr><tr><td>a</td><td>b</td></tr></table>"
    )
    assert style == "table" and crits == ["a | b"] and counts["header_rows"] == 1
    style, crits, _ = parse_acceptance("<ul><li>one</li><li>two &amp; three</li></ul>")
    assert style == "list" and crits == ["one", "two & three"]
    style, crits, _ = parse_acceptance("Scenario: ok\nGiven x\nThen y\nScenario: bad\nThen z")
    assert style == "gherkin" and len(crits) == 2 and crits[0].startswith("Scenario: ok")
    assert parse_acceptance("plain line")[0] == "prose"


def test_canonical_backlog_round_trip(tmp_path: Path) -> None:
    doc = {
        "kind": "pbd.backlog",
        "items": [
            {
                "id": "PBD-ITEM-0000000000AA",
                "type": "story",
                "title": "t",
                "parent": None,
                "description": {"value": "d"},
                "fields": {"priority": {"value": 1, "state": "confirmed"}},
            }
        ],
        "criteria": [{"parent": "PBD-ITEM-0000000000AA", "text": "c1"}],
    }
    out = load_backlog(_write(tmp_path, "b.json", json.dumps(doc)))
    assert out["format"] == "pbd.backlog"
    assert out["items"][0]["fields_raw"] == {"priority": 1}
    assert [c["raw"] for c in out["criteria"]] == ["c1"]
