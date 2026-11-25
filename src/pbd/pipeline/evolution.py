"""Evolution engine: what changed in the sources, what it means for the backlog, what is now stale.

1. ``diff_sources`` compares two local versions of the selected sources member by member (after
   the same text extraction readers use). It separates **identical**, **formatting-only** (same
   text after whitespace/case/punctuation normalisation — an administrative change) and
   **content** changes with line hunks. Interpreting a content change is agent work.
2. The agent writes an evolution proposal: the refinement operations plus lineage and decisions
   (``split_item``, ``merge_items``, ``add_decision`` superseding claims, ``supersede_item``).
   ``plan`` (refine) keeps every ID, refuses recreating an item only because its title changed,
   refuses silent overwrites of human edits and never deletes; ``summarize`` classifies the result
   as create / update / unchanged / conflict / deferred per item.
3. ``stale_artifacts`` finds plans, packages, publication plans and refinement plans bound to the
   previous backlog digest: they are invalid and must be produced again (approvals included).
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pbd.core.canonical import bytes_digest, digest
from pbd.pipeline import extract
from pbd.pipeline.refine import base_digest

DIGEST_KEYS = ("backlog_digest", "base_digest")


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).casefold()
    t = re.sub(r"[\s ]+", " ", t)
    return re.sub(r"[*_`#>|\-–—•·.,;:!?\"'()\[\]]", "", t).strip()


def _members(root: Path) -> dict[str, Path]:
    if root.is_file():
        return {root.name: root}
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}


def _text(path: Path) -> str:
    try:
        return extract.extract(path.name, path.read_bytes()).text
    except (extract.ExtractionError, ValueError, OSError):
        return ""


def diff_sources(old: Path, new: Path, selectors: list[str]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for sel in selectors:
        o, n = Path(old) / sel, Path(new) / sel
        if not o.exists() and not n.exists():
            raise FileNotFoundError(f"source {sel} exists in neither version")
        om = _members(o) if o.exists() else {}
        nm = _members(n) if n.exists() else {}
        members = []
        for name in sorted(set(om) | set(nm)):
            if name not in om:
                members.append(
                    {"path": name, "change": "added", "new_digest": bytes_digest(nm[name].read_bytes())}
                )
                continue
            if name not in nm:
                members.append(
                    {"path": name, "change": "removed", "old_digest": bytes_digest(om[name].read_bytes())}
                )
                continue
            ob, nb = om[name].read_bytes(), nm[name].read_bytes()
            entry: dict[str, Any] = {
                "path": name,
                "old_digest": bytes_digest(ob),
                "new_digest": bytes_digest(nb),
            }
            if ob == nb:
                entry["change"] = "identical"
            else:
                ot, nt = _text(om[name]), _text(nm[name])
                if _norm(ot) == _norm(nt):
                    entry["change"] = "formatting_only"
                else:
                    entry["change"] = "content"
                    hunks = []
                    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                        a=ot.splitlines(), b=nt.splitlines(), autojunk=False
                    ).get_opcodes():
                        if tag == "equal":
                            continue
                        hunks.append(
                            {
                                "op": tag,
                                "old_lines": [i1 + 1, i2],
                                "new_lines": [j1 + 1, j2],
                                "old": ot.splitlines()[i1:i2][:20],
                                "new": nt.splitlines()[j1:j2][:20],
                            }
                        )
                    entry["hunks"] = hunks
            members.append(entry)
        changes = {m["change"] for m in members}
        sources.append(
            {
                "selector": sel,
                "change": "content"
                if changes & {"content", "added", "removed"}
                else ("formatting_only" if "formatting_only" in changes else "identical"),
                "members": members,
            }
        )
    doc = {
        "kind": "pbd.source-diff",
        "sources": sources,
        "summary": {
            k: sum(1 for s in sources for m in s["members"] if m["change"] == k)
            for k in ("identical", "formatting_only", "content", "added", "removed")
        },
        "note": (
            "formatting_only means the extracted text is equal after normalisation "
            "(an administrative change); "
            "what a content change means for the backlog is decided by an agent reading the new version."
        ),
    }
    doc["diff_digest"] = digest(sources)
    return doc


def summarize(base: dict[str, Any], plan_doc: dict[str, Any]) -> dict[str, Any]:
    """Per-item evolution classification for a refinement/evolution plan (no new judgement)."""
    touched: dict[str, list[str]] = {}
    created: list[str] = []
    for c in plan_doc["changes"]:
        if c["op"] in ("add_item",):
            created.append(c["target"])
        elif c["op"] == "split_item":
            created += c["after"]["split_into"]
            touched.setdefault(c["target"], []).append(c["key"])
        elif c["op"] == "merge_items":
            created.append(c["target"])
            for t in c["before"]:
                touched.setdefault(t, []).append(c["key"])
        elif c["op"] != "add_decision" and not c.get("noop"):
            touched.setdefault(c["target"], []).append(c["key"])
    explicit = {c["target"] for c in plan_doc["changes"] if c.get("requires_explicit_approval")}
    rows = []
    for item in base["items"]:
        iid = item["id"]
        if iid in explicit:
            action = "conflict"
        elif iid in touched:
            action = "update"
        else:
            action = "unchanged"
        rows.append({"item": iid, "title": item["title"], "action": action, "changes": touched.get(iid, [])})
    rows += [{"item": i, "title": "", "action": "create", "changes": []} for i in created]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    return {
        "kind": "pbd.evolution-summary",
        "base_digest": base_digest(base),
        "plan_digest": plan_doc["plan_digest"],
        "counts": counts,
        "items": rows,
        "deletions": 0,
        "decisions": [c["after"] for c in plan_doc["changes"] if c["op"] == "add_decision"],
        "note": "No item is deleted; superseded items stay visible with their lineage.",
    }


def stale_artifacts(directory: Path, backlog: dict[str, Any]) -> dict[str, Any]:
    """JSON artifacts under ``directory`` bound to a backlog digest other than the current one."""
    current = {
        base_digest(backlog),
        digest({k: v for k, v in backlog.items() if k not in ("keys", "_digest")}),
    }
    stale, current_ok = [], []
    for path in sorted(Path(directory).rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        bound = [doc[k] for k in DIGEST_KEYS if isinstance(doc.get(k), str)]
        if not bound:
            continue
        rel = path.relative_to(directory).as_posix()
        if any(b in current for b in bound):
            current_ok.append(rel)
        else:
            stale.append(
                {
                    "path": rel,
                    "kind": doc.get("kind"),
                    "bound_to": bound[0],
                    "approval": (doc.get("approval") or {}).get("state"),
                }
            )
    return {
        "kind": "pbd.staleness",
        "backlog_digest": sorted(current)[0],
        "stale": stale,
        "current": current_ok,
        "note": "Stale plans, packages and approvals must be produced again; old approvals never carry over.",
    }
