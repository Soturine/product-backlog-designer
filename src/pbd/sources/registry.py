"""Build canonical source records from explicit selectors.

Inventory produces a complete member ledger with ``pending`` status. It deliberately
sets ``read_status = "not_read"``: only a semantic reader (the host agent) may advance
reading status, and partial inventory blocks completeness claims.
"""

from __future__ import annotations

from typing import Any

from pbd.core.identity import derive
from pbd.sources.scope import Scope, SourceInventory

AUTHORITIES = {
    "functional",
    "technical",
    "decision",
    "implementation_evidence",
    "existing_backlog",
    "corroboration",
    "instructions",
    "other",
}


def source_id_for(selector: str) -> str:
    return derive("source", {"selector": selector})


def source_record(inv: SourceInventory, authority: str, version: str | None = None) -> dict[str, Any]:
    if authority not in AUTHORITIES:
        raise ValueError(f"unknown authority role: {authority}")
    ledger = inv.ledger_digest()
    record: dict[str, Any] = {
        "id": source_id_for(inv.selector),
        "selector": inv.selector,
        "kind": inv.kind,
        "authority": authority,
        "version": version or ledger.removeprefix("sha256:")[:16],
        "digest": ledger,
        "read_status": "unreadable" if inv.errors and not inv.members else "not_read",
        "members": [m.to_json() for m in inv.members],
    }
    omissions = list(inv.errors) + [
        f"{m.path}: {m.reason}" for m in inv.members if m.status in ("rejected", "skipped", "unreadable")
    ]
    if omissions:
        record["omissions"] = omissions
    return record


def build_sources(scope: Scope, selections: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """``selections`` is a list of (selector, authority). One logical source per selector."""
    records = []
    seen: set[str] = set()
    for selector, authority in selections:
        inv = scope.inventory(selector)
        if inv.selector in seen:
            raise ValueError(f"source selected twice: {inv.selector}")
        seen.add(inv.selector)
        records.append(source_record(inv, authority))
    return records
