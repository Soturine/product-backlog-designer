"""Re-render recorded benchmark runs with the current renderer, into a SEPARATE directory.

The recorded runs (``benchmarks/runs/m1``) are immutable evidence: this tool only reads them. Each
re-render is labelled as such (renderer version, source case, date-free) so it is never mistaken
for a new agent-led execution. Design keys (US1, AC2...) are recovered exactly, because canonical
IDs are derived from ``(kind, run_id, key)``; candidate keys come from the recorded review.

Usage: python tools/rerender.py [benchmarks/runs/m1] [benchmarks/rerender/m1]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pbd import __version__
from pbd.core.identity import KINDS, derive
from pbd.render.report_html import render_report

ROOT = Path(__file__).resolve().parents[1]


def _candidate_keys(review: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for e in review.get("items", []) + review.get("criteria", []):
        keys.add(e["key"])
    for o in review.get("independent_obligations", []):
        keys.update(o.get("matched_claims", []))
        keys.update(o.get("covered_by", []))
    for f in review.get("findings", []):
        keys.update(f.get("affects", []))
    for d in review.get("duplicates", []):
        keys.update(d.get("items", []))
    return keys


def recover_keys(backlog: dict[str, Any], review: dict[str, Any]) -> dict[str, str]:
    ids = {i["id"] for i in backlog["items"]} | {c["id"] for c in backlog["criteria"]}
    ids |= {c["id"] for c in backlog["claims"]} | {q["id"] for q in backlog["questions"]}
    ids |= {d["id"] for d in backlog.get("decisions", [])}
    found: dict[str, str] = {}
    candidates = _candidate_keys(review) | {f"C{n}" for n in range(1, 400)} | {f"Q{n}" for n in range(1, 100)}
    candidates |= {f"DEC{n}" for n in range(1, 50)} | {f"D{n}" for n in range(1, 50)}
    for key in candidates:
        for kind in KINDS:
            pid = derive(kind, {"run": backlog["run_id"], "key": key})
            if pid in ids:
                found[pid] = key
    return found


def rerender(case: Path, out: Path) -> dict[str, Any]:
    backlog = json.loads((case / "backlog.json").read_text(encoding="utf-8"))
    review = json.loads((case / "review.json").read_text(encoding="utf-8"))
    gates = json.loads((case / "gates.json").read_text(encoding="utf-8"))
    metrics = json.loads((case / "metrics.json").read_text(encoding="utf-8"))
    keys = recover_keys(backlog, review)
    ctx = {
        "backlog": backlog,
        "keys": keys,
        "review": review,
        "gates": gates,
        "metrics": metrics,
        "title": f"{case.name} (re-render)",
        "limitations": [
            f"Re-render of recorded run {case.name} with renderer {__version__}; not a new execution."
        ],
        "azure": None,
        "version": __version__,
        "mode": "generate",
    }
    html = render_report(ctx)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.html").write_text(html, encoding="utf-8")
    items = len(backlog["items"]) + len(backlog["criteria"])
    mapped = sum(1 for i in backlog["items"] + backlog["criteria"] if i["id"] in keys)
    return {"case": case.name, "keys_recovered": f"{mapped}/{items}", "bytes": len(html.encode("utf-8"))}


def main(argv: list[str]) -> int:
    src = Path(argv[0]) if argv else ROOT / "benchmarks" / "runs" / "m1"
    dst = Path(argv[1]) if len(argv) > 1 else ROOT / "benchmarks" / "rerender" / "m1"
    rows = [rerender(c, dst / c.name) for c in sorted(src.iterdir()) if (c / "backlog.json").exists()]
    lines = [
        "# M1 re-render",
        "",
        f"Re-render of the recorded M1 runs in `{src.relative_to(ROOT).as_posix()}` "
        f"with renderer `{__version__}`.",
        "The recorded runs are unchanged; these pages are NOT new agent executions. Content, gates and",
        "metrics are the recorded ones; only the presentation is new. Integration package previews are",
        "not re-rendered (the recorded runs keep their own packages).",
        "",
        "| case | design keys recovered | report bytes |",
        "|---|---|---|",
        *(f"| {r['case']} | {r['keys_recovered']} | {r['bytes']} |" for r in rows),
    ]
    (dst / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
