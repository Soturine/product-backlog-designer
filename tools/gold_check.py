"""Validate benchmark gold files: every gold quote must exist in its synthetic source.

Usage: python tools/gold_check.py   (prints resolved line numbers; exit 1 on any unresolved quote)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pbd.pipeline.extract import extract  # noqa: E402
from pbd.pipeline.reading import normalize_for_match  # noqa: E402


def resolve(case_dir: Path, source: str, quote: str) -> int | None:
    path = case_dir / "sources" / source
    text = extract(path.name, path.read_bytes())
    needle = normalize_for_match(quote)
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in normalize_for_match(line):
            return number
    return None


def check(
    gold_dir: Path = ROOT / "benchmarks" / "gold", cases_dir: Path = ROOT / "benchmarks" / "cases"
) -> list[str]:
    problems = []
    for gold_path in sorted(gold_dir.glob("*.json")):
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        case_dir = cases_dir / gold["case"]
        selectors = {s["selector"] for s in gold["sources"]}
        for ob in gold["obligations"]:
            if not any(ob["source"] == s or ob["source"].startswith(s + "/") for s in selectors):
                problems.append(
                    f"{gold['case']} {ob['id']}: source {ob['source']} is not a declared selector"
                )
                continue
            line = resolve(case_dir, ob["source"], ob["quote"])
            if line is None:
                problems.append(f"{gold['case']} {ob['id']}: quote not found in {ob['source']}")
    return problems


if __name__ == "__main__":
    issues = check()
    print("\n".join(issues) or "all gold quotes resolve")
    raise SystemExit(1 if issues else 0)
