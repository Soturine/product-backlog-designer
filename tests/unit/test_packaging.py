"""Every non-Python runtime file must be declared as package data (regression: profiles missing)."""

from __future__ import annotations

import fnmatch
import tomllib

from tests.conftest import REPO_ROOT


def test_package_data_covers_all_runtime_resources() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["pbd"]
    root = REPO_ROOT / "src" / "pbd"
    resources = [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts
    ]
    missing = [r for r in resources if not any(fnmatch.fnmatch(r, pat) for pat in patterns)]
    assert resources and missing == [], missing
