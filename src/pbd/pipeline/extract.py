"""Deterministic text extraction for source members (support for readers, never a semantic verdict).

Supported: UTF-8 text formats and ``.docx`` (paragraphs and table rows). Anything else is
reported as needing a transcription; it is never silently skipped.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

TEXT_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".text",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".kt",
    ".cs",
    ".go",
    ".rb",
    ".php",
    ".sql",
    ".feature",
    ".ini",
    ".toml",
    ".cfg",
    ".conf",
    ".ps1",
    ".sh",
    ".mmd",
    ".puml",
    ".rst",
    ".adoc",
    ".properties",
    ".env.example",
}
MAX_TEXT_BYTES = 8 * 1024 * 1024
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ExtractionError(ValueError):
    pass


def extractor_for(name: str) -> str | None:
    suffix = PurePosixPath(name.lower()).suffix
    if suffix == ".docx":
        return "docx"
    if suffix in TEXT_SUFFIXES or PurePosixPath(name).name.lower() in {
        "readme",
        "license",
        "makefile",
        "dockerfile",
    }:
        return "text"
    return None


def _decode(data: bytes) -> str:
    if len(data) > MAX_TEXT_BYTES:
        raise ExtractionError("member exceeds text size limit")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError("not valid UTF-8 text") from exc
    if "\x00" in text:
        raise ExtractionError("binary content")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            info = zf.getinfo("word/document.xml")
            if info.file_size > MAX_TEXT_BYTES:
                raise ExtractionError("document part exceeds size limit")
            xml = zf.read(info)
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ExtractionError("not a readable .docx package") from exc
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise ExtractionError("DTD/entity declarations are not accepted")
    root = ElementTree.fromstring(xml)  # noqa: S314 - DTD/entities rejected above; size bounded
    lines: list[str] = []
    body = root.find(f"{_W}body")
    for block in list(body) if body is not None else []:
        if block.tag == f"{_W}p":
            lines.append("".join(t.text or "" for t in block.iter(f"{_W}t")))
        elif block.tag == f"{_W}tbl":
            for row in block.iter(f"{_W}tr"):
                cells = [
                    "".join(t.text or "" for t in cell.iter(f"{_W}t")).strip() for cell in row.iter(f"{_W}tc")
                ]
                lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def extract(name: str, data: bytes) -> str:
    kind = extractor_for(name)
    if kind == "text":
        return _decode(data)
    if kind == "docx":
        return _docx(data)
    raise ExtractionError("no text extractor for this format; provide a transcription")


def read_member_bytes(source_path: Path, kind: str, member: str) -> bytes:
    """Read one member of a file, directory or zip archive source (tar members via tarfile)."""
    if kind == "file":
        return source_path.read_bytes()
    if kind == "directory":
        target = (source_path / member).resolve()
        target.relative_to(source_path.resolve())
        return target.read_bytes()
    if zipfile.is_zipfile(source_path):
        with zipfile.ZipFile(source_path) as zf:
            return zf.read(member)
    import tarfile

    with tarfile.open(source_path) as tf:
        stream = tf.extractfile(member)
        if stream is None:
            raise ExtractionError("archive member has no data")
        return stream.read()


def chunks(line_count: int, size: int) -> list[list[int]]:
    """Bounded, contiguous line ranges covering 1..line_count."""
    if line_count <= 0:
        return []
    return [[start, min(start + size - 1, line_count)] for start in range(1, line_count + 1, size)]
