"""Canonical JSON serialization and content digests.

Canonical form: UTF-8, sorted object keys, no insignificant whitespace, no NaN/Infinity,
Unicode preserved (not escaped) and normalized to NFC for strings. The digest of a value
therefore does not depend on dict ordering or on platform locale.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from pathlib import Path
from typing import Any

DIGEST_PREFIX = "sha256:"


class CanonicalError(ValueError):
    """Raised when a value cannot be represented canonically."""


def _normalize(value: Any, path: str = "$") -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, bool) or value is None or isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise CanonicalError(f"non-finite number at {path}")
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalError(f"non-string key at {path}")
            nkey = unicodedata.normalize("NFC", key)
            if nkey in out:
                raise CanonicalError(f"duplicate key after normalization at {path}: {nkey!r}")
            out[nkey] = _normalize(item, f"{path}.{nkey}")
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise CanonicalError(f"unsupported type {type(value).__name__} at {path}")


def canonical_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes for ``value``."""
    normalized = _normalize(value)
    text = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    """Deterministic human-readable JSON (sorted keys, 2-space indent, trailing newline)."""
    normalized = _normalize(value)
    text = json.dumps(normalized, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    return (text + "\n").encode("utf-8")


def digest(value: Any) -> str:
    """Stable content digest of a JSON-compatible value."""
    return DIGEST_PREFIX + hashlib.sha256(canonical_bytes(value)).hexdigest()


def bytes_digest(data: bytes) -> str:
    return DIGEST_PREFIX + hashlib.sha256(data).hexdigest()


def file_digest(path: Path, chunk_size: int = 1 << 16) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            hasher.update(chunk)
    return DIGEST_PREFIX + hasher.hexdigest()


def _reject_constant(token: str) -> Any:
    raise CanonicalError(f"non-finite number {token} not allowed")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise CanonicalError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out


def loads_strict(data: bytes | str) -> Any:
    """Parse JSON rejecting duplicate keys and NaN/Infinity (fail closed)."""
    if isinstance(data, bytes):
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            # fail closed (guessing cp1252 could silently alter quotes) but say how to fix it
            raise CanonicalError(
                f"payload is not UTF-8 (byte 0x{data[exc.start]:02x} at offset {exc.start}; Windows tools "
                "often write cp1252): save the file as UTF-8, e.g. open(path, 'w', encoding='utf-8')"
            ) from exc
    else:
        text = data
    return json.loads(text, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant)


def load_json_file(path: Path) -> Any:
    return loads_strict(Path(path).read_bytes())
