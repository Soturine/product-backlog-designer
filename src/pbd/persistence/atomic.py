"""Atomic file writes and a hash-chained append-only journal."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Any

from pbd.core.canonical import CanonicalError, canonical_bytes, digest, loads_strict, pretty_bytes

GENESIS = "sha256:" + "0" * 64


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` so readers observe either the old or the new file, never a partial one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def atomic_write_json(path: Path, value: Any) -> str:
    """Write deterministic JSON atomically and return its content digest."""
    atomic_write_bytes(path, pretty_bytes(value))
    return digest(value)


class JournalError(RuntimeError):
    pass


class Journal:
    """Append-only JSON-lines journal; each entry chains the digest of the previous one.

    Tampering, truncation in the middle or reordering is detected by :meth:`verify`.
    A torn final line (crash during append) is reported, not silently dropped.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for number, line in enumerate(self.path.read_bytes().splitlines(), start=1):
            if not line.strip():
                continue
            try:
                out.append(loads_strict(line))
            except (ValueError, CanonicalError) as exc:
                raise JournalError(f"unreadable journal line {number}: {exc}") from exc
        return out

    def verify(self) -> str:
        """Verify the chain and return the head digest."""
        prev = GENESIS
        for index, entry in enumerate(self.entries()):
            body = {k: v for k, v in entry.items() if k != "entry_digest"}
            if entry.get("prev") != prev:
                raise JournalError(f"chain broken at entry {index}")
            if digest(body) != entry.get("entry_digest"):
                raise JournalError(f"entry {index} digest mismatch")
            if entry.get("seq") != index:
                raise JournalError(f"sequence gap at entry {index}")
            prev = entry["entry_digest"]
        return prev

    def append(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        head = self.verify()
        seq = len(self.entries())
        body = {"seq": seq, "prev": head, "event": event, "payload": payload}
        entry = {**body, "entry_digest": digest(body)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab") as handle:
            handle.write(canonical_bytes(entry) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        return entry
