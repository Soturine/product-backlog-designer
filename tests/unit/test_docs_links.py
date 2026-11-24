"""Every relative Markdown link in the repository resolves to an existing file (offline)."""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import REPO_ROOT

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SKIP_PARTS = {".git", ".venv", ".pbd", "node_modules", ".pytest_cache", ".hypothesis"}


def markdown_files() -> list[Path]:
    return [p for p in REPO_ROOT.rglob("*.md") if not SKIP_PARTS & set(p.relative_to(REPO_ROOT).parts)]


def test_relative_markdown_links_resolve() -> None:
    broken = []
    for md in markdown_files():
        text = md.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            if path and not (md.parent / path).exists():
                broken.append(f"{md.relative_to(REPO_ROOT).as_posix()} -> {target}")
    assert broken == [], "\n".join(broken)
