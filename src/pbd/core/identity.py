"""Stable opaque identity.

PBD identifiers look like ``PBD-STORY-7K3M9QX2C4HD`` and are:

* opaque: they never encode titles, positions or array indexes;
* stable: once minted they are persisted and never recomputed from mutable content;
* separate from tracker identifiers, which live in :class:`ExternalRef` with their own
  ``system``/``namespace``. A tracker ID is never a PBD ID and vice versa.

``mint`` creates a new random identifier. ``derive`` creates a deterministic identifier
from an explicit, caller-chosen *anchor* (for example a source ID plus locator) so that a
re-import of the same anchor yields the same ID. Titles must not be used as anchors;
``derive`` rejects anchors that carry only a title.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass

# Crockford base32 without I, L, O, U.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_BODY_LEN = 12

KINDS: dict[str, str] = {
    "source": "SRC",
    "claim": "CLM",
    "epic": "EPIC",
    "feature": "FEAT",
    "story": "STORY",
    "enabler": "ENAB",
    "spike": "SPIKE",
    "bug": "BUG",
    "task": "TASK",
    "criterion": "AC",
    "relation": "REL",
    "question": "Q",
    "decision": "DEC",
    "finding": "FND",
    "run": "RUN",
    "plan": "PLAN",
    "operation": "OP",
    "receipt": "RCPT",
}

ID_PATTERN = r"^PBD-(" + "|".join(sorted(set(KINDS.values()))) + r")-[0-9A-HJKMNP-TV-Z]{12}$"
_ID_RE = re.compile(ID_PATTERN)
_FORBIDDEN_ANCHOR_KEYS = {"title", "name", "position", "index", "order"}


class IdentityError(ValueError):
    pass


def _encode(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    chars = []
    for _ in range(_BODY_LEN):
        number, rem = divmod(number, 32)
        chars.append(_ALPHABET[rem])
    return "".join(reversed(chars))


def _prefix(kind: str) -> str:
    try:
        return KINDS[kind]
    except KeyError as exc:
        raise IdentityError(f"unknown identity kind: {kind!r}") from exc


def mint(kind: str) -> str:
    """Mint a new random opaque identifier for ``kind``."""
    return f"PBD-{_prefix(kind)}-{_encode(secrets.token_bytes(8))}"


def derive(kind: str, anchor: dict[str, str]) -> str:
    """Deterministically derive an ID from an explicit provenance anchor.

    ``anchor`` must contain at least one key and no title/position-like keys, e.g.
    ``{"source": "PBD-SRC-...", "locator": "section 3.2 row 4"}``.
    """
    if not anchor:
        raise IdentityError("anchor must not be empty")
    bad = _FORBIDDEN_ANCHOR_KEYS.intersection(k.lower() for k in anchor)
    if bad:
        raise IdentityError(f"identity anchors must not use title/position keys: {sorted(bad)}")
    material = "\x1f".join(f"{k}\x1e{anchor[k]}" for k in sorted(anchor))
    raw = hashlib.sha256(f"pbd-identity-v1\x1d{kind}\x1d{material}".encode()).digest()[:8]
    return f"PBD-{_prefix(kind)}-{_encode(raw)}"


def is_pbd_id(value: object) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value))


def kind_of(value: str) -> str:
    if not is_pbd_id(value):
        raise IdentityError(f"not a PBD identifier: {value!r}")
    prefix = value.split("-")[1]
    for kind, pfx in KINDS.items():
        if pfx == prefix:
            return kind
    raise IdentityError(f"unknown prefix: {prefix}")  # pragma: no cover


@dataclass(frozen=True)
class ExternalRef:
    """Native tracker identity in its own namespace (never merged with PBD IDs)."""

    system: str  # e.g. "azure-devops", "mock"
    namespace: str  # opaque target identity, e.g. a project GUID; synthetic in tests
    native_id: str
    revision: int | None = None

    def __post_init__(self) -> None:
        if not self.system or not self.namespace or not self.native_id:
            raise IdentityError("external refs require system, namespace and native_id")
        if is_pbd_id(self.native_id):
            raise IdentityError("a PBD identifier cannot be used as a native tracker ID")

    def key(self) -> tuple[str, str, str]:
        return (self.system, self.namespace, self.native_id)
