from __future__ import annotations

import io
import os
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from pbd.sources.registry import build_sources, source_id_for
from pbd.sources.scope import ArchiveLimits, Scope, ScopeError
from pbd.validation.schema import validate

pytestmark = pytest.mark.security


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    (root / "docs" / "sub").mkdir(parents=True)
    (root / "docs" / "prd.md").write_text("# PRD fictício\nRegra A.\n", encoding="utf-8")
    (root / "docs" / "sub" / "anexo.csv").write_text("id,regra\n1,b\n", encoding="utf-8")
    (root / "docs" / ".git").mkdir()
    (root / "docs" / ".git" / "config").write_text("x", encoding="utf-8")
    (tmp_path / "outside.md").write_text("segredo fora do escopo", encoding="utf-8")
    return root


def tree(root: Path) -> list[tuple[str, int]]:
    """Snapshot of the workspace parent (paths and sizes) to prove a refusal wrote nothing."""
    base = root.parent
    return sorted(
        (p.relative_to(base).as_posix(), p.stat().st_size if p.is_file() else -1) for p in base.rglob("*")
    )


def _symlink(link: Path, target: Path, is_dir: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=is_dir)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable on this host: {exc}")


def test_file_and_directory_inventory_with_member_ledger(ws: Path) -> None:
    scope = Scope(ws)
    inv = scope.inventory("docs")
    assert inv.kind == "directory"
    paths = {m.path: m.status for m in inv.members}
    assert paths == {".git/": "skipped", "prd.md": "pending", "sub/anexo.csv": "pending"}
    single = scope.inventory("docs/prd.md")
    assert single.kind == "file" and single.members[0].digest


@pytest.mark.parametrize("selector", ["../outside.md", "docs/../../outside.md"])
def test_traversal_escape_rejected(ws: Path, selector: str) -> None:
    before = tree(ws)
    with pytest.raises(ScopeError):
        Scope(ws).resolve(selector)
    assert tree(ws) == before


def test_absolute_path_outside_rejected(ws: Path) -> None:
    before = tree(ws)
    with pytest.raises(ScopeError):
        Scope(ws).resolve(str(ws.parent / "outside.md"))
    assert tree(ws) == before


def test_missing_selector_reported_not_substituted(ws: Path) -> None:
    before = tree(ws)
    with pytest.raises(ScopeError, match="does not exist"):
        Scope(ws).resolve("docs/tdd.md")
    assert tree(ws) == before and not (ws / "docs" / "tdd.md").exists()


def test_null_byte_and_empty_selector_rejected(ws: Path) -> None:
    before = tree(ws)
    for bad in ["", "docs/\x00prd.md"]:
        with pytest.raises(ScopeError):
            Scope(ws).resolve(bad)
    assert tree(ws) == before


def test_selected_symlink_rejected(ws: Path) -> None:
    _symlink(ws / "link.md", ws.parent / "outside.md")
    with pytest.raises(ScopeError):
        Scope(ws).resolve("link.md")


def test_symlink_member_not_followed(ws: Path) -> None:
    _symlink(ws / "docs" / "escape.md", ws.parent / "outside.md")
    _symlink(ws / "docs" / "escdir", ws.parent, is_dir=True)
    members = {m.path: (m.status, m.reason) for m in Scope(ws).inventory("docs").members}
    assert members["escape.md"] == ("rejected", "link not followed")
    assert members["escdir/"] == ("rejected", "link not followed")
    assert not any("outside" in p for p in members)


def _zip(path: Path, entries: list[tuple[str, bytes, int | None]]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data, mode in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if mode is not None:
                info.external_attr = mode << 16
            zf.writestr(info, data)


def test_zip_inventory_rejects_unsafe_members(ws: Path) -> None:
    # the duplicate member is deliberate (zipfile warns about it while writing the fixture)
    with pytest.warns(UserWarning, match="Duplicate name"):
        _make_unsafe_zip(ws)
    _check_unsafe_zip(ws)


def _make_unsafe_zip(ws: Path) -> None:
    _zip(
        ws / "pacote.zip",
        [
            ("ok/regras.md", "Regra Ç".encode(), None),
            ("../escape.md", b"x", None),
            ("/abs.md", b"x", None),
            ("C:/win.md", b"x", None),
            ("link.md", b"../../outside.md", stat.S_IFLNK | 0o777),
            ("ok/regras.md", b"dup", None),
            ("inner.zip", b"PK", None),
        ],
    )


def _check_unsafe_zip(ws: Path) -> None:
    inv = Scope(ws).inventory("pacote.zip")
    assert inv.kind == "archive"
    status = [(m.path, m.status, m.reason) for m in inv.members]
    assert ("ok/regras.md", "pending", None) in status
    assert sum(1 for s in status if s[2] == "unsafe member path") == 3
    assert ("link.md", "rejected", "link entry not followed") in status
    assert ("ok/regras.md", "rejected", "duplicate member name") in status
    assert ("inner.zip", "skipped", "nested archive not expanded") in status
    assert not (ws.parent / "escape.md").exists()  # nothing extracted


def test_zip_bomb_ratio_and_member_limits(ws: Path) -> None:
    _zip(ws / "bomba.zip", [("big.txt", b"0" * 2_000_000, None)])
    inv = Scope(ws, ArchiveLimits(max_ratio=50)).inventory("bomba.zip")
    assert inv.members[0].status == "rejected" and "ratio" in str(inv.members[0].reason)
    _zip(ws / "muitos.zip", [(f"f{i}.txt", b"x", None) for i in range(5)])
    limited = Scope(ws, ArchiveLimits(max_members=3)).inventory("muitos.zip")
    assert limited.errors and not limited.members


def test_tar_inventory_rejects_traversal_links_and_devices(ws: Path) -> None:
    path = ws / "pacote.tar"
    with tarfile.open(path, "w") as tf:

        def add(name: str, data: bytes = b"x", kind: bytes = tarfile.REGTYPE, linkname: str = "") -> None:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.linkname = linkname
            info.size = len(data) if kind == tarfile.REGTYPE else 0
            tf.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)

        add("ok.md", "ação".encode())
        add("../../evil.md")
        add("sym", kind=tarfile.SYMTYPE, linkname="/etc/passwd")
        add("hard", kind=tarfile.LNKTYPE, linkname="ok.md")
        add("fifo", kind=tarfile.FIFOTYPE)
    status = {m.path: (m.status, m.reason) for m in Scope(ws).inventory("pacote.tar").members}
    assert status["ok.md"][0] == "pending"
    assert status["../../evil.md"] == ("rejected", "unsafe member path")
    assert status["sym"] == ("rejected", "link entry not followed")
    assert status["hard"] == ("rejected", "link entry not followed")
    assert status["fifo"] == ("rejected", "special file entry")


def test_corrupt_archive_is_reported_unreadable(ws: Path) -> None:
    (ws / "quebrado.zip").write_bytes(b"PK\x03\x04garbage")
    record = build_sources(Scope(ws), [("quebrado.zip", "functional")])[0]
    assert record["read_status"] == "unreadable"
    assert record["omissions"]


def test_source_records_are_schema_valid_and_never_marked_read(ws: Path) -> None:
    records = build_sources(Scope(ws), [("docs", "functional"), ("docs/prd.md", "technical")])
    for r in records:
        assert r["read_status"] == "not_read"
        assert all(m["status"] != "read" for m in r["members"])
    assert records[0]["id"] == source_id_for("docs")
    doc = {
        "schema_version": "1.0.0",
        "kind": "pbd.backlog",
        "run_id": "PBD-RUN-000000000001",
        "language": "pt-BR",
        "sources": records,
        "claims": [],
        "items": [],
        "criteria": [],
        "relations": [],
        "questions": [],
        "decisions": [],
        "findings": [],
    }
    assert validate("backlog", doc) == []


def test_duplicate_selection_and_unknown_authority_rejected(ws: Path) -> None:
    before = tree(ws)
    with pytest.raises(ValueError):
        build_sources(Scope(ws), [("docs", "functional"), ("docs/", "functional")])
    with pytest.raises(ValueError):
        build_sources(Scope(ws), [("docs", "boss-said-so")])
    assert tree(ws) == before


def test_ledger_digest_changes_when_member_changes(ws: Path) -> None:
    scope = Scope(ws)
    before = scope.inventory("docs").ledger_digest()
    (ws / "docs" / "sub" / "anexo.csv").write_text("id,regra\n1,c\n", encoding="utf-8")
    assert scope.inventory("docs").ledger_digest() != before


def test_windows_junction_member_and_selector_rejected(ws: Path) -> None:
    winapi = pytest.importorskip("_winapi")
    if not hasattr(winapi, "CreateJunction"):
        pytest.skip("junctions unsupported")
    winapi.CreateJunction(str(ws.parent), str(ws / "docs" / "juncao"))
    members = {m.path: (m.status, m.reason) for m in Scope(ws).inventory("docs").members}
    assert members["juncao/"] == ("rejected", "link not followed")
    assert not any("outside" in p for p in members)
    with pytest.raises(ScopeError):
        Scope(ws).resolve("docs/juncao/outside.md")
