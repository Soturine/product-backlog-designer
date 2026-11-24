"""Process profiles: canonical type and field mapping per target process.

A profile is a default, never proof of the target's configuration. Custom profiles are JSON
files with the same shape and are validated before use.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

CANONICAL_TYPES = ("epic", "feature", "story", "enabler", "spike", "bug", "task")
FIELD_KEYS = (
    "title",
    "description",
    "acceptance",
    "priority",
    "story_points",
    "original_estimate",
    "activity",
    "tags",
    "risk",
    "business_value",
    "time_criticality",
    "value_area",
)

PROFILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "name", "tracker", "types", "fields", "acceptance_types", "verified"],
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
        "name": {"type": "string", "minLength": 1},
        "tracker": {"enum": ["none", "azure-devops", "github", "jira", "other"]},
        "types": {
            "type": "object",
            "additionalProperties": False,
            "required": list(CANONICAL_TYPES),
            "properties": {t: {"type": ["string", "null"]} for t in CANONICAL_TYPES},
        },
        "type_tags": {"type": "object", "additionalProperties": {"type": "string"}},
        "fields": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "description"],
            "properties": {k: {"type": ["string", "null"]} for k in FIELD_KEYS},
        },
        "acceptance_types": {"type": "array", "uniqueItems": True, "items": {"enum": list(CANONICAL_TYPES)}},
        "estimate_field": {"type": "object", "additionalProperties": {"type": "string"}},
        "activities": {"type": "array", "items": {"type": "string"}},
        "verified": {"type": "boolean"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
}


class ProfileError(ValueError):
    pass


@cache
def builtin_profiles() -> dict[str, dict[str, Any]]:
    text = resources.files("pbd.profiles").joinpath("builtin.json").read_text(encoding="utf-8")
    return {p["id"]: p for p in json.loads(text)["profiles"]}


def validate_profile(profile: Any) -> list[str]:
    errors = [
        f"{'/'.join(map(str, e.absolute_path)) or '$'}: {e.message}"
        for e in Draft202012Validator(PROFILE_SCHEMA).iter_errors(profile)
    ]
    if not errors and profile["fields"].get("acceptance") is None and profile["acceptance_types"]:
        errors.append("acceptance_types requires an acceptance field")
    return errors


def load_profile(ref: str) -> dict[str, Any]:
    """Load a builtin profile by id, or a custom profile from a JSON file path."""
    builtins = builtin_profiles()
    if ref in builtins:
        return builtins[ref]
    path = Path(ref)
    if not path.is_file():
        raise ProfileError(f"unknown profile {ref!r}; builtins: {sorted(builtins)}")
    profile = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_profile(profile)
    if errors:
        raise ProfileError("invalid custom profile: " + "; ".join(errors))
    result: dict[str, Any] = profile
    return result


def native_type(profile: dict[str, Any], canonical: str) -> str | None:
    value = profile["types"].get(canonical)
    return value if isinstance(value, str) else None


def has_acceptance_field(profile: dict[str, Any], canonical: str) -> bool:
    return bool(profile["fields"].get("acceptance")) and canonical in profile.get("acceptance_types", [])
