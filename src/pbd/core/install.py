"""Install the skill folder (SKILL.md, procedures, docs and runtime source) for an agent host.

Installing the Python package (``pip install``) only provides the ``pbd`` command; an agent host
discovers the *skill* from a folder containing SKILL.md. This copies that folder.
"""

from __future__ import annotations

import shutil
from pathlib import Path

SKILL_NAME = "product-backlog-designer"
INCLUDE = (
    "SKILL.md",
    "README.md",
    "README.pt-BR.md",
    "ATTRIBUTION.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "procedures",
    "entrypoints",
    "docs",
    "src",
)
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", ".pytest_cache", ".mypy_cache")


class InstallError(RuntimeError):
    pass


def skill_source_root() -> Path:
    """Repository/skill root containing SKILL.md (when running from a checkout or an installed skill)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "SKILL.md").is_file() and (parent / "procedures").is_dir():
            return parent
    raise InstallError("SKILL.md not found next to the runtime; install from a repository checkout")


def target_dir(scope: str, project: Path | None = None, home: Path | None = None) -> Path:
    if scope == "project":
        return Path(project or Path.cwd()) / ".claude" / "skills" / SKILL_NAME
    if scope == "user":
        return Path(home or Path.home()) / ".claude" / "skills" / SKILL_NAME
    raise InstallError("scope must be project or user")


def install(target: Path, *, source: Path | None = None, force: bool = False) -> list[str]:
    source = source or skill_source_root()
    target = Path(target)
    if target.exists():
        if not force:
            raise InstallError(f"{target} exists; pass --force to replace it")
        if not (target / "SKILL.md").is_file():
            raise InstallError(f"refusing to replace {target}: it is not a skill folder")
        shutil.rmtree(target)
    target.mkdir(parents=True)
    copied = []
    for name in INCLUDE:
        src = source / name
        if src.is_dir():
            shutil.copytree(src, target / name, ignore=IGNORE)
        elif src.is_file():
            shutil.copy2(src, target / name)
        else:
            continue
        copied.append(name)
    if "SKILL.md" not in copied:
        raise InstallError("source has no SKILL.md")
    return copied
