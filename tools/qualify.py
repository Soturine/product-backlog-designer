"""Local qualification: one command for every deterministic check, with a JSON summary.

Usage: python tools/qualify.py [--mutation] [--playwright] [--out DIR]

Runs ruff (lint + format check), mypy (strict), pytest with branch coverage, the privacy scan
and optionally the mutation check. Never contacts a network service; CI is not required.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, argv: list[str], results: dict[str, dict[str, object]]) -> bool:
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
    results[name] = {
        "command": " ".join(argv[1:]) if argv[0] == sys.executable else " ".join(argv),
        "exit": proc.returncode,
        "tail": tail,
    }
    print(f"[{'ok' if proc.returncode == 0 else 'FAIL'}] {name}: {tail[-1] if tail else ''}", flush=True)
    return proc.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutation", action="store_true")
    parser.add_argument("--playwright", action="store_true")
    parser.add_argument("--out", default=".pbd/qualification")
    args = parser.parse_args(argv)
    py = sys.executable
    results: dict[str, dict[str, object]] = {}
    marker = [] if args.playwright else ["-m", "not playwright"]
    ok = all(
        [
            run("ruff", [py, "-m", "ruff", "check", "src", "tests", "tools"], results),
            run("format", [py, "-m", "ruff", "format", "--check", "src", "tests", "tools"], results),
            run("mypy", [py, "-m", "mypy"], results),
            run(
                "pytest+coverage",
                [
                    py,
                    "-m",
                    "coverage",
                    "run",
                    "--branch",
                    "--source=src/pbd",
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    *marker,
                ],
                results,
            ),
            run("coverage", [py, "-m", "coverage", "report", "--format=total"], results),
            run("privacy", [py, "-m", "pbd", "privacy-scan", "."], results),
        ]
    )
    if args.mutation:
        ok = run("mutation", [py, "tools/mutation_check.py"], results) and ok
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ok": ok,
        "checks": results,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (ROOT / ".coverage").unlink(missing_ok=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
