"""Reader ledger submission (one logical reader per declared source).

A reader catalogs what the source says; it never designs work items or decides coverage.
The runtime verifies, deterministically and all-or-nothing:

* the ledger targets a source of this run and its exact digest;
* every member of the source is accounted for exactly once; ``read`` means every line was
  covered by ``lines_read``; ``partial``/``unreadable``/``skipped`` require a reason;
* every obligation/ambiguity/exclusion cites a member, a line range inside the file and inside
  the lines actually read, and a ``quote`` that really occurs in those lines (whitespace- and
  case-insensitive). A fabricated quote is rejected.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from pbd import vocab
from pbd.core.canonical import digest
from pbd.pipeline.extract import NATIVE_METHODS, READING_METHODS, READING_POLICY
from pbd.pipeline.run import Run, RunError, require_stage

READER_FIELDS = {
    "source_id",
    "source_digest",
    "reader",
    "members",
    "obligations",
    "ambiguities",
    "exclusions",
    "notes",
}
FORBIDDEN = {
    "items",
    "work_items",
    "stories",
    "epics",
    "features",
    "tasks",
    "criteria",
    "coverage",
    "dispositions",
    "gates",
    "backlog",
    "claims",
    "findings",
}
CATEGORIES = vocab.claim_categories()
MODALITIES = vocab.READER_MODALITIES
UNCERTAINTY = vocab.READER_UNCERTAINTY
MEMBER_STATUS = vocab.MEMBER_STATUS
INDEPENDENCE = vocab.INDEPENDENCE
_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,40}$")


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = re.sub(r"[*_`>#|]", " ", text)  # markdown decoration may be dropped when quoting
    return re.sub(r"\s+", " ", text).strip()


def _covered(ranges: list[list[int]]) -> set[int]:
    lines: set[int] = set()
    for start, end in ranges:
        lines.update(range(start, end + 1))
    return lines


def _member_lines(run: Run, member: dict[str, Any]) -> list[str]:
    text = run.path(member["text_ref"]).read_text(encoding="utf-8")
    return text.splitlines()


def _check_reading(path: str, entry: dict[str, Any], meta: dict[str, Any], vt: Any) -> list[str]:
    """Native-first reading declaration of one member (method, tool, limitations)."""
    status = entry.get("status")
    if status not in ("read", "partial"):
        return []
    reading = entry.get("reading")
    if not isinstance(reading, dict):
        return [
            f"member {path}: declare how it was read in reading {{method: native|native_vision|"
            "extracted_text, tool, limitations}"
        ]
    method = reading.get("method")
    errors = []
    if method not in READING_METHODS:
        errors.append(f"member {path}: reading.method must be one of {sorted(READING_METHODS)}")
    if not str(reading.get("tool", "")).strip():
        errors.append(f"member {path}: reading.tool (the host capability actually used) is required")
    limitations = reading.get("limitations")
    if not isinstance(limitations, list):
        errors.append(f"member {path}: reading.limitations must be a list (empty when there are none)")
        limitations = []
    fmt = meta.get("format", "text")
    policy = READING_POLICY.get(fmt, READING_POLICY["text"])
    if status == "read" and method not in NATIVE_METHODS:
        if not policy["fallback_complete"]:
            errors.append(
                f"member {path}: a {fmt} member is not completely read from its extracted text "
                f"({policy['extracted_layer']}); open the original natively or report it partial"
            )
        elif fmt != "text" and not limitations:
            errors.append(
                f"member {path}: read from the {fmt} extraction fallback; declare its limitations "
                f"({policy['extracted_layer']})"
            )
    if meta.get("visual") and method != "native_vision":
        errors.append(f"member {path}: visual members are read with native_vision only")
    if vt is not None and method not in NATIVE_METHODS:
        errors.append(f"member {path}: a visual_transcription requires a native reading method")
    return errors


def quote_verification(
    run: Run, source_id: str, member_entry: dict[str, Any] | None, loc: dict[str, Any], quote: str
) -> str:
    """'mechanical' when the quote is in the cited extracted lines, else 'agent_transcription'."""
    src = next((s for s in run.inventory()["sources"] if s["id"] == source_id), None)
    meta = next((m for m in (src or {}).get("members_text", []) if m["path"] == loc.get("member")), None)
    start = loc.get("line_start")
    if meta and meta.get("readable") and isinstance(start, int):
        end = loc.get("line_end", start)
        lines = _member_lines(run, meta)
        if normalize_for_match(quote) in normalize_for_match(" ".join(lines[start - 1 : end])):
            return "mechanical"
    return "agent_transcription"


def validate_ledger(run: Run, ledger: Any) -> list[str]:
    if not isinstance(ledger, dict):
        return ["ledger must be a JSON object"]
    errors: list[str] = []
    forbidden = sorted(set(ledger) & FORBIDDEN)
    if forbidden:
        errors.append(f"readers catalog sources only; remove design/coverage decisions {forbidden}")
    unknown = sorted(set(ledger) - READER_FIELDS - FORBIDDEN)
    if unknown:
        errors.append(f"unknown fields {unknown}")
    sources = {s["id"]: s for s in run.inventory()["sources"]}
    src = sources.get(ledger.get("source_id"))
    if src is None:
        return [*errors, f"source_id {ledger.get('source_id')!r} is not a source of this run"]
    if ledger.get("source_digest") != src["digest"]:
        errors.append("source_digest does not match the inventoried source (stale or wrong source)")
    reader = ledger.get("reader")
    if (
        not isinstance(reader, dict)
        or not str(reader.get("agent", "")).strip()
        or not str(reader.get("model", "")).strip()
    ):
        errors.append("reader.agent and reader.model (the model that actually ran) are required")
    elif reader.get("independence") not in INDEPENDENCE:
        errors.append(f"reader.independence must be one of {sorted(INDEPENDENCE)}")

    members = {m["path"]: m for m in src["members_text"]}
    reported: dict[str, dict[str, Any]] = {}
    for entry in ledger.get("members") or []:
        path = entry.get("path") if isinstance(entry, dict) else None
        if path not in members:
            errors.append(f"member {path!r} does not belong to this source")
            continue
        if path in reported:
            errors.append(f"member {path} reported twice")
            continue
        reported[str(path)] = entry
        status = entry.get("status")
        meta = members[path]
        if status not in MEMBER_STATUS:
            errors.append(f"member {path}: status must be one of {sorted(MEMBER_STATUS)}")
            continue
        vt = entry.get("visual_transcription")
        if vt is not None and not (
            isinstance(vt, dict)
            and vt.get("method") == "agent_vision"
            and str(vt.get("text", "")).strip()
            and str(vt.get("model", "")).strip()
        ):
            errors.append(f"member {path}: visual_transcription needs method agent_vision, model and text")
            continue
        reading_errors = _check_reading(str(path), entry, meta, vt)
        if reading_errors:
            errors.extend(reading_errors)
            continue
        if meta.get("visual"):
            if status in ("read", "partial") and vt is None:
                errors.append(
                    f"member {path} is visual ({meta.get('reason')}); read it with agent vision and add "
                    "visual_transcription, or report it unreadable"
                )
                continue
            if status != "read" and not str(entry.get("reason", "")).strip():
                errors.append(f"member {path}: status {status} requires a reason")
            continue
        if not meta["readable"] and status in ("read", "partial"):
            errors.append(
                f"member {path} has no extractable text ({meta.get('reason')}); report it unreadable"
            )
            continue
        if status == "read" and meta.get("gaps") and vt is None:
            errors.append(
                f"member {path} has extraction gaps {meta['gaps']}; it can only be read with a "
                "visual_transcription of those parts, otherwise report it partial with a reason"
            )
            continue
        if status != "read" and not str(entry.get("reason", "")).strip():
            errors.append(f"member {path}: status {status} requires a reason")
        if status in ("read", "partial"):
            ranges = entry.get("lines_read")
            if not isinstance(ranges, list) or not all(
                isinstance(r, list)
                and len(r) == 2
                and all(isinstance(x, int) for x in r)
                and 1 <= r[0] <= r[1] <= meta["lines"]
                for r in ranges
            ):
                errors.append(
                    f"member {path}: lines_read must be [start, end] ranges within 1..{meta['lines']}"
                )
                continue
            if status == "read" and _covered(ranges) != set(range(1, meta["lines"] + 1)):
                errors.append(
                    f"member {path}: status read requires every line 1..{meta['lines']} in lines_read"
                )
    missing = sorted(set(members) - set(reported))
    if missing:
        errors.append(f"members not accounted for: {missing}")
    if errors:
        return errors

    keys: set[str] = set()
    cache: dict[str, list[str]] = {}
    for section in ("obligations", "ambiguities", "exclusions"):
        for index, entry in enumerate(ledger.get(section) or []):
            label = f"{section}[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{label} must be an object")
                continue
            if section == "obligations":
                key = entry.get("key")
                if not isinstance(key, str) or not _KEY.match(key):
                    errors.append(f"{label}: key must be a short identifier")
                elif key in keys:
                    errors.append(f"{label}: duplicate key {key}")
                else:
                    keys.add(key)
                if entry.get("category") not in CATEGORIES:
                    errors.append(f"{label}: category must be one of {sorted(CATEGORIES)}")
                if entry.get("modality", "must") not in MODALITIES:
                    errors.append(f"{label}: modality must be one of {sorted(MODALITIES)}")
                if entry.get("uncertainty", "confirmed") not in UNCERTAINTY:
                    errors.append(f"{label}: uncertainty must be one of {sorted(UNCERTAINTY)}")
            if not str(entry.get("text", "")).strip():
                errors.append(f"{label}: text is required")
            errors.extend(_check_locator(run, label, entry, members, reported, cache))
    return errors


def _check_locator(
    run: Run,
    label: str,
    entry: dict[str, Any],
    members: dict[str, dict[str, Any]],
    reported: dict[str, dict[str, Any]],
    cache: dict[str, list[str]],
) -> list[str]:
    loc = entry.get("locator")
    if not isinstance(loc, dict):
        return [f"{label}: locator with member and line_start is required"]
    member = members.get(str(loc.get("member")))
    if member is not None and member.get("visual"):
        vt = (reported.get(member["path"]) or {}).get("visual_transcription") or {}
        vquote = str(entry.get("quote", ""))
        if len(vquote.strip()) < 3 or normalize_for_match(vquote) not in normalize_for_match(
            str(vt.get("text", ""))
        ):
            return [f"{label}: quote must occur in the member's visual_transcription"]
        return []
    if member is None or not member["readable"]:
        return [f"{label}: locator member {loc.get('member')!r} is not a readable member of this source"]
    vt_text = str(((reported.get(member["path"]) or {}).get("visual_transcription") or {}).get("text", ""))
    quote_any = str(entry.get("quote", ""))
    if loc.get("line_start") is None:
        # a citation of content the text layer does not carry (figure, drawn diagram, scanned page):
        # only valid from the reader's own native transcription, and classified as such
        if not (loc.get("page") or loc.get("section") or loc.get("table")):
            return [f"{label}: locator needs line_start, or page/section/table for transcribed content"]
        if len(quote_any.strip()) < 3 or normalize_for_match(quote_any) not in normalize_for_match(vt_text):
            return [
                f"{label}: without line numbers the quote must occur in the member's visual_transcription"
            ]
        return []
    start, end = loc.get("line_start"), loc.get("line_end", loc.get("line_start"))
    if not (isinstance(start, int) and isinstance(end, int) and 1 <= start <= end <= member["lines"]):
        return [f"{label}: lines {start}-{end} are outside {member['path']} (1..{member['lines']})"]
    page = loc.get("page")
    if page is not None and member.get("pages"):
        span = next((p for p in member["pages"] if p[0] == page), None)
        if span is None or not (span[1] <= start and end <= span[2]):
            return [f"{label}: page {page} does not contain lines {start}-{end}"]
    read_ranges = reported[member["path"]].get("lines_read") or []
    if not set(range(start, end + 1)) <= _covered(read_ranges):
        return [f"{label}: cites lines {start}-{end} that the reader did not report as read"]
    quote = entry.get("quote")
    if not isinstance(quote, str) or len(quote.strip()) < 3:
        return [f"{label}: a verbatim quote (>= 3 chars) from the cited lines is required"]
    lines = cache.setdefault(member["path"], _member_lines(run, member))
    window = normalize_for_match(" ".join(lines[start - 1 : end]))
    if normalize_for_match(quote) not in window:
        return [
            f"{label}: quote not found in {member['path']} lines {start}-{end} (fabricated or wrong locator)"
        ]
    return []


def submit_ledger(run: Run, ledger: dict[str, Any]) -> dict[str, Any]:
    require_stage(run, "inventory")
    if run.stage_status("reading") == "complete":
        raise RunError("reading is complete; start a new run to change reader ledgers")
    errors = validate_ledger(run, ledger)
    if errors:
        raise RunError("reader ledger rejected (nothing recorded)", errors)
    rel = f"stages/reading/{ledger['source_id']}.json"
    run.write_artifact(rel, ledger)
    for m in ledger["members"]:
        if m.get("visual_transcription"):
            run.state.manifest["limitations"].append(
                f"member {m['path']} read by agent vision ({m['visual_transcription']['model']}); quotes are "
                "checked against the agent's transcription, not deterministically against the original"
            )
    for entry in run.state.manifest["sources"]:
        if entry["source_id"] == ledger["source_id"]:
            entry["reader"].update(
                status="complete" if all(m["status"] == "read" for m in ledger["members"]) else "partial",
                independence=ledger["reader"]["independence"],
                agent=str(ledger["reader"]["agent"]),
                members_read=sum(1 for m in ledger["members"] if m["status"] == "read"),
            )
    run.state.journal.append(
        "reader_ledger", {"source_id": ledger["source_id"], "digest": run.artifact_digest(rel)}
    )
    pending = [
        s["id"] for s in run.inventory()["sources"] if not run.path(f"stages/reading/{s['id']}.json").exists()
    ]
    if not pending:
        ledgers = [run.artifact_digest(f"stages/reading/{s['id']}.json") for s in run.inventory()["sources"]]
        complete = all(e["reader"]["status"] == "complete" for e in run.state.manifest["sources"])
        run.state.manifest["status"]["source_coverage"] = (
            "complete_reading" if complete else "incomplete_reading"
        )
        run.save()
        run.state.complete("reading", str(run.artifact_digest("sources/inventory.json")), digest(ledgers))
    else:
        run.save()
    run.write_work_order()
    return {
        "accepted": ledger["source_id"],
        "pending_sources": pending,
        "obligations": len(ledger.get("obligations") or []),
    }
