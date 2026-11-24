"""Source allowlist, canonical path validation, symlink and archive safety.

Rules (fail closed):

* Only explicitly selected selectors are in scope; nothing is substituted when missing.
* Every selector must resolve inside the workspace; ``..``/absolute escapes are rejected.
* Symlinks (and Windows junctions/reparse points that resolve outside) are never followed.
  A selected symlink is rejected; a symlink member of a directory is recorded as rejected.
* Archives are inspected in place, never extracted. Entries with absolute paths, drive
  letters, ``..`` traversal, links or device types are rejected; member count, per-member
  size, total size and compression ratio are bounded.
* Each selector is ONE logical source (a directory or archive counts as one), with a
  complete member ledger.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import stat
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from pbd.core.canonical import digest, file_digest

IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".pbd",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")


class ScopeError(ValueError):
    """Selector outside the authorized scope or otherwise unsafe."""


@dataclass(frozen=True)
class ArchiveLimits:
    max_members: int = 10_000
    max_member_bytes: int = 256 * 1024 * 1024
    max_total_bytes: int = 1024 * 1024 * 1024
    max_ratio: float = 200.0


@dataclass
class Member:
    path: str
    status: str  # pending | rejected | skipped | unreadable
    digest: str | None = None
    bytes: int | None = None
    media_type: str | None = None
    reason: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"path": self.path, "status": self.status}
        if self.digest:
            out["digest"] = self.digest
        if self.bytes is not None:
            out["bytes"] = self.bytes
        if self.media_type:
            out["media_type"] = self.media_type
        if self.reason:
            out["reason"] = self.reason
        return out


@dataclass
class SourceInventory:
    selector: str
    kind: str
    members: list[Member] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def ledger_digest(self) -> str:
        return digest([[m.path, m.status, m.digest] for m in sorted(self.members, key=lambda m: m.path)])

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for m in self.members:
            out[m.status] = out.get(m.status, 0) + 1
        return out


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)  # Python 3.12+
    if is_junction is not None and is_junction():
        return True
    try:
        attrs = int(getattr(os.lstat(path), "st_file_attributes", 0))
    except OSError:
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _media_type(name: str) -> str:
    guessed, _ = mimetypes.guess_type(name)
    return guessed or "application/octet-stream"


def is_archive(path: Path) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(suffix) for suffix in ARCHIVE_SUFFIXES)


def _safe_member_name(name: str) -> str | None:
    """Return a normalized POSIX member path, or None if unsafe."""
    if not name or "\x00" in name:
        return None
    unified = name.replace("\\", "/")
    if unified.startswith("/") or (len(unified) > 1 and unified[1] == ":"):
        return None
    parts = [p for p in PurePosixPath(unified).parts if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


class Scope:
    """Explicit allowlist of selectors rooted in one workspace."""

    def __init__(self, workspace: Path, limits: ArchiveLimits | None = None) -> None:
        self.workspace = Path(workspace).resolve(strict=True)
        self.limits = limits or ArchiveLimits()

    def resolve(self, selector: str) -> Path:
        if not selector or "\x00" in selector:
            raise ScopeError("empty or invalid selector")
        raw = Path(selector)
        candidate = raw if raw.is_absolute() else self.workspace / raw
        # Reject links anywhere along the selected path before resolving.
        probe = candidate
        while True:
            if (
                (probe.exists() or probe.is_symlink())
                and _is_link_or_junction(probe)
                and probe != self.workspace
            ):
                raise ScopeError(f"selector traverses a link: {selector}")
            if probe.parent == probe or probe == self.workspace:
                break
            probe = probe.parent
        resolved = candidate.resolve(strict=False)
        if not _within(resolved, self.workspace):
            raise ScopeError(f"selector escapes the workspace: {selector}")
        if not resolved.exists():
            raise ScopeError(f"selected source does not exist: {selector}")
        return resolved

    def relative(self, path: Path) -> str:
        return path.relative_to(self.workspace).as_posix() or "."

    # ------------------------------------------------------------------
    def inventory(self, selector: str) -> SourceInventory:
        path = self.resolve(selector)
        rel = self.relative(path)
        if path.is_dir():
            return self._inventory_dir(rel, path)
        if is_archive(path):
            return self._inventory_archive(rel, path)
        inv = SourceInventory(rel, "file")
        inv.members.append(self._file_member(path, path.name))
        return inv

    def _file_member(self, path: Path, name: str) -> Member:
        try:
            size = path.stat().st_size
            return Member(name, "pending", file_digest(path), size, _media_type(name))
        except OSError as exc:
            return Member(name, "unreadable", reason=f"{type(exc).__name__}")

    def _inventory_dir(self, rel: str, root: Path) -> SourceInventory:
        inv = SourceInventory(rel, "directory")
        for current, dirs, files in os.walk(root, followlinks=False):
            cur = Path(current)
            keep = []
            for d in sorted(dirs):
                dpath = cur / d
                member = dpath.relative_to(root).as_posix()
                if _is_link_or_junction(dpath):
                    inv.members.append(Member(member + "/", "rejected", reason="link not followed"))
                elif d in IGNORED_DIRS:
                    inv.members.append(Member(member + "/", "skipped", reason="ignored directory"))
                else:
                    keep.append(d)
            dirs[:] = keep
            for f in sorted(files):
                fpath = cur / f
                member = fpath.relative_to(root).as_posix()
                if _is_link_or_junction(fpath):
                    inv.members.append(Member(member, "rejected", reason="link not followed"))
                elif not fpath.is_file():
                    inv.members.append(Member(member, "rejected", reason="not a regular file"))
                else:
                    inv.members.append(self._file_member(fpath, member))
        inv.members.sort(key=lambda m: m.path)
        return inv

    def _inventory_archive(self, rel: str, path: Path) -> SourceInventory:
        inv = SourceInventory(rel, "archive")
        try:
            if zipfile.is_zipfile(path):
                self._inventory_zip(inv, path)
            elif tarfile.is_tarfile(path):
                self._inventory_tar(inv, path)
            else:
                inv.errors.append("unrecognized archive format")
        except (zipfile.BadZipFile, tarfile.TarError, OSError, EOFError) as exc:
            inv.errors.append(f"archive unreadable: {type(exc).__name__}")
        inv.members.sort(key=lambda m: m.path)
        return inv

    def _hash_stream(self, stream: Any, limit: int) -> tuple[str, int] | None:
        hasher = hashlib.sha256()
        total = 0
        while chunk := stream.read(1 << 16):
            total += len(chunk)
            if total > limit:
                return None
            hasher.update(chunk)
        return "sha256:" + hasher.hexdigest(), total

    def _inventory_zip(self, inv: SourceInventory, path: Path) -> None:
        lim = self.limits
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if len(infos) > lim.max_members:
                inv.errors.append(f"archive has {len(infos)} members, limit {lim.max_members}")
                return
            total = 0
            seen: set[str] = set()
            for info in infos:
                name = _safe_member_name(info.filename)
                mode = (info.external_attr >> 16) & 0xFFFF
                shown = name or info.filename
                if name is None:
                    inv.members.append(Member(shown, "rejected", reason="unsafe member path"))
                    continue
                if stat.S_ISLNK(mode):
                    inv.members.append(Member(name, "rejected", reason="link entry not followed"))
                    continue
                if info.is_dir():
                    continue
                if name in seen:
                    inv.members.append(Member(name, "rejected", reason="duplicate member name"))
                    continue
                seen.add(name)
                if info.file_size > lim.max_member_bytes:
                    inv.members.append(Member(name, "rejected", reason="member exceeds size limit"))
                    continue
                if info.compress_size and info.file_size / info.compress_size > lim.max_ratio:
                    inv.members.append(Member(name, "rejected", reason="compression ratio exceeds limit"))
                    continue
                total += info.file_size
                if total > lim.max_total_bytes:
                    inv.errors.append("archive total size exceeds limit; remaining members not inventoried")
                    return
                if is_archive(Path(name)):
                    inv.members.append(
                        Member(name, "skipped", reason="nested archive not expanded", bytes=info.file_size)
                    )
                    continue
                with zf.open(info) as stream:
                    hashed = self._hash_stream(stream, lim.max_member_bytes)
                if hashed is None:
                    inv.members.append(Member(name, "rejected", reason="declared size mismatch"))
                    continue
                inv.members.append(Member(name, "pending", hashed[0], hashed[1], _media_type(name)))

    def _inventory_tar(self, inv: SourceInventory, path: Path) -> None:
        lim = self.limits
        with tarfile.open(path) as tf:
            total = 0
            count = 0
            seen: set[str] = set()
            for info in tf:
                count += 1
                if count > lim.max_members:
                    inv.errors.append(f"archive exceeds member limit {lim.max_members}")
                    return
                name = _safe_member_name(info.name)
                if name is None:
                    inv.members.append(Member(info.name, "rejected", reason="unsafe member path"))
                    continue
                if info.issym() or info.islnk():
                    inv.members.append(Member(name, "rejected", reason="link entry not followed"))
                    continue
                if info.isdir():
                    continue
                if not info.isfile():
                    inv.members.append(Member(name, "rejected", reason="special file entry"))
                    continue
                if name in seen:
                    inv.members.append(Member(name, "rejected", reason="duplicate member name"))
                    continue
                seen.add(name)
                if info.size > lim.max_member_bytes:
                    inv.members.append(Member(name, "rejected", reason="member exceeds size limit"))
                    continue
                total += info.size
                if total > lim.max_total_bytes:
                    inv.errors.append("archive total size exceeds limit; remaining members not inventoried")
                    return
                if is_archive(Path(name)):
                    inv.members.append(
                        Member(name, "skipped", reason="nested archive not expanded", bytes=info.size)
                    )
                    continue
                stream = tf.extractfile(info)
                if stream is None:
                    inv.members.append(Member(name, "unreadable", reason="no data stream"))
                    continue
                hashed = self._hash_stream(stream, lim.max_member_bytes)
                if hashed is None:
                    inv.members.append(Member(name, "rejected", reason="declared size mismatch"))
                    continue
                inv.members.append(Member(name, "pending", hashed[0], hashed[1], _media_type(name)))
