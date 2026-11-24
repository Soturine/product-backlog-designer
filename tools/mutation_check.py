"""Reproducible mutation check: inject each catalogued defect, run the suite, require a failure.

Usage: python tools/mutation_check.py [--only ID ...] [--json OUT]

Each mutant is applied to an isolated copy of the repository (never the working tree), so an
interrupted run cannot leave mutated source behind. Exit status 0 only if every mutant is killed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tests" / "mutation" / "mutants.json"
COPY_IGNORE = shutil.ignore_patterns(
    ".git",
    ".venv",
    ".pbd",
    "pbd-output",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    "build",
    "dist",
    "*.egg-info",
)


def load_mutants() -> list[dict[str, str]]:
    data: list[dict[str, str]] = json.loads(CATALOG.read_text(encoding="utf-8"))["mutants"]
    return data


def apply(root: Path, mutant: dict[str, str]) -> None:
    path = root / mutant["file"]
    text = path.read_text(encoding="utf-8")
    if mutant["old"] not in text:
        raise SystemExit(f"mutant {mutant['id']} no longer applies to {mutant['file']}")
    path.write_text(text.replace(mutant["old"], mutant["new"], 1), encoding="utf-8")


def run_one(mutant: dict[str, str]) -> bool:
    with tempfile.TemporaryDirectory(prefix="pbd-mut-") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(ROOT, work, ignore=COPY_IGNORE)
        apply(work, mutant)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-m", "not playwright"],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
            env={**_clean_env(), "PYTHONPATH": str(work / "src")},
        )
        return result.returncode != 0


def _clean_env() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH"}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--json")
    args = parser.parse_args(argv)
    mutants = [m for m in load_mutants() if not args.only or m["id"] in args.only]
    results = {}
    for mutant in mutants:
        killed = run_one(mutant)
        results[mutant["id"]] = "KILLED" if killed else "SURVIVED"
        print(f"{mutant['id']}: {results[mutant['id']]}", flush=True)
    survivors = [k for k, v in results.items() if v == "SURVIVED"]
    summary = {
        "mutants": len(results),
        "killed": len(results) - len(survivors),
        "survivors": survivors,
        "results": results,
    }
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}))
    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 1 if survivors else 0


if __name__ == "__main__":
    raise SystemExit(main())
