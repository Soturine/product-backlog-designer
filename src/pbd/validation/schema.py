"""Load bundled v1 schemas and validate documents (offline: no remote $ref retrieval)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

SCHEMA_FILES = {
    "defs": "defs.schema.json",
    "backlog": "backlog.schema.json",
    "run-manifest": "run-manifest.schema.json",
    "gate-report": "gate-report.schema.json",
    "publication-plan": "publication-plan.schema.json",
    "publication-receipt": "publication-receipt.schema.json",
}
DOCUMENT_KINDS = {
    "pbd.backlog": "backlog",
    "pbd.run-manifest": "run-manifest",
    "pbd.gate-report": "gate-report",
    "pbd.publication-plan": "publication-plan",
    "pbd.publication-receipt": "publication-receipt",
}


@dataclass(frozen=True)
class Issue:
    path: str
    message: str
    code: str = "schema"

    def __str__(self) -> str:
        return f"[{self.code}] {self.path}: {self.message}"


@cache
def load_schema(name: str) -> dict[str, Any]:
    if name not in SCHEMA_FILES:
        raise KeyError(f"unknown schema: {name}")
    text = resources.files("pbd.schemas.v1").joinpath(SCHEMA_FILES[name]).read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


def _refuse_retrieval(uri: str) -> Resource[Any]:
    # Fail closed: schemas must never be fetched from the network.
    raise NoSuchResource(ref=uri)  # type: ignore[call-arg]


@cache
def registry() -> Registry[Any]:
    reg: Registry[Any] = Registry(retrieve=_refuse_retrieval)  # type: ignore[call-arg]
    for name in SCHEMA_FILES:
        schema = load_schema(name)
        reg = reg.with_resource(schema["$id"], Resource.from_contents(schema))
    return reg


@cache
def validator(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=registry())


def _json_path(parts: Any) -> str:
    out = "$"
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


def validate(name: str, document: Any) -> list[Issue]:
    errors = sorted(validator(name).iter_errors(document), key=lambda e: (list(e.absolute_path), e.message))
    return [Issue(_json_path(e.absolute_path), e.message) for e in errors]


def schema_for_document(document: Any) -> str | None:
    if isinstance(document, dict):
        return DOCUMENT_KINDS.get(str(document.get("kind")))
    return None
