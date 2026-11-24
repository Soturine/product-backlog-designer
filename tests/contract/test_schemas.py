"""Schema contract tests: bundled schemas are well-formed, valid fixtures pass, every
invalid mutation is rejected with the expected issue code."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from pbd.validation.gates import check_gate_report
from pbd.validation.invariants import check_backlog
from pbd.validation.schema import SCHEMA_FILES, load_schema, schema_for_document, validate
from tests.conftest import FIXTURES, load_valid

pytestmark = pytest.mark.contract
DOCS = [n for n in SCHEMA_FILES if n != "defs"]
CASES = json.loads((FIXTURES / "schemas" / "invalid-cases.json").read_text(encoding="utf-8"))["cases"]


def all_issues(name: str, doc: dict[str, Any]) -> list[Any]:
    issues = validate(name, doc)
    if issues:
        return issues
    if name == "backlog":
        return check_backlog(doc)
    if name == "gate-report":
        return check_gate_report(doc)
    return []


def apply(doc: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any]:
    doc = copy.deepcopy(doc)
    for op in ops:
        *parents, last = op["path"]
        node: Any = doc
        for key in parents:
            node = node[key]
        if op["op"] == "set":
            node[last] = op["value"]
        elif op["op"] == "del":
            del node[last]
        elif op["op"] == "append":
            node[last].append(op["value"])
        else:  # pragma: no cover
            raise AssertionError(op)
    return doc


@pytest.mark.parametrize("name", list(SCHEMA_FILES))
def test_schema_is_valid_draft_2020_12(name: str) -> None:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].startswith("urn:pbd:schema:v1:")


@pytest.mark.parametrize("name", list(SCHEMA_FILES))
def test_schemas_reference_only_bundled_urns(name: str) -> None:
    text = json.dumps(load_schema(name))
    refs = [part.split('"')[0] for part in text.split('"$ref": "')[1:]]
    assert refs, name if name != "defs" else "defs uses internal refs"
    for ref in refs:
        assert ref.startswith(("#", "urn:pbd:schema:v1:")), ref


@pytest.mark.parametrize("name", DOCS)
def test_valid_fixture_passes_all_checks(name: str) -> None:
    doc = load_valid(name)
    assert schema_for_document(doc) == name
    assert all_issues(name, doc) == []


def test_invalid_case_ids_are_unique() -> None:
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_invalid_case_is_rejected_with_expected_code(case: dict[str, Any]) -> None:
    doc = apply(load_valid(case["base"]), case["ops"])
    codes = {issue.code for issue in all_issues(case["base"], doc)}
    assert case["expect"] in codes, f"expected {case['expect']}, got {codes or 'no issues'}"


def test_every_document_kind_has_invalid_cases() -> None:
    assert {c["base"] for c in CASES} == set(DOCS)


def test_schema_does_not_fetch_remote_refs() -> None:
    doc = load_valid("backlog")
    doc["items"][0]["description"] = {"$ref": "https://example.invalid/evil.json"}
    # Unknown keys inside a richText object are rejected; resolution is never attempted.
    assert validate("backlog", doc)
