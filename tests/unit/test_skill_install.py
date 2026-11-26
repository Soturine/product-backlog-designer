from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbd.cli import main
from pbd.core.install import InstallError, install, skill_source_root, target_dir


def test_skill_root_and_targets(tmp_path: Path) -> None:
    root = skill_source_root()
    assert (root / "SKILL.md").is_file()
    assert target_dir("project", tmp_path) == tmp_path / ".claude" / "skills" / "product-backlog-designer"
    with pytest.raises(InstallError):
        target_dir("global")


def test_install_copies_skill_and_runtime(tmp_path: Path) -> None:
    target = tmp_path / "skills" / "product-backlog-designer"
    copied = install(target)
    assert {"SKILL.md", "procedures", "src", "docs"} <= set(copied)
    assert (target / "procedures" / "reader.md").is_file()
    assert (target / "src" / "pbd" / "cli.py").is_file()
    assert not list(target.rglob("__pycache__"))
    text = (target / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: product-backlog-designer\n")
    for link in ("procedures/orchestrator.md", "procedures/reader.md", "docs/usage.md"):
        assert (target / link).is_file(), link
    with pytest.raises(InstallError, match="exists"):
        install(target)
    install(target, force=True)


def test_install_refuses_to_replace_non_skill_folder(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (other / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(InstallError, match="not a skill folder"):
        install(other, force=True)
    assert (other / "keep.txt").exists()


def test_cli_skill_install(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["skill", "install", "--scope", "project", "--project", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert Path(out["installed"]).name == "product-backlog-designer"
    assert main(["skill", "install", "--scope", "project", "--project", str(tmp_path)]) == 3


def test_packaged_skill_assets_in_sync_with_repository() -> None:
    """Drift guard: run tools/sync_skill_assets.py after editing SKILL.md, procedures, entrypoints or docs."""
    from tools.sync_skill_assets import current, expected

    assert current() == expected()


def test_install_from_packaged_assets_without_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (ledger QL-006): wheel installs have no checkout around the runtime."""
    import pbd.core.install as inst

    packaged = Path(inst.__file__).resolve().parents[1] / "skill_assets"
    monkeypatch.setattr(inst, "skill_source_root", lambda: packaged)
    copied = inst.install(tmp_path / "skill")
    assert (
        "SKILL.md" in copied
        and "procedures" in copied
        and (tmp_path / "skill" / "procedures" / "reader.md").is_file()
    )


def test_installed_skill_never_points_to_a_bundled_source_tree() -> None:
    """QL-015: an installed skill folder carries no src/ or pyproject; instructions must not assume one."""
    from tools.sync_skill_assets import ROOT

    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "<this skill folder>/src" not in text and "pip install <this skill folder>" not in text
    assert "instructions only" in text
