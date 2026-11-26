"""Deterministic text extraction for source members (support for readers, never a semantic verdict).

Every extraction returns explicit ``gaps`` for content that could not be turned into text (PDF pages
without a text layer, images embedded in documents, unsupported parts). A member with gaps can
never be certified as fully read unless the reader supplies a transcription for them.

Supported: UTF-8/UTF-16 text (with a recorded cp1252 fallback), ``.docx`` (body paragraphs and
tables, headers, footers, footnotes, endnotes, comments), ``.xlsx`` (every sheet, row and cell,
shared strings, formulas shown with their cached value), ``.pdf`` with a selectable text layer
(optional ``pypdf``; page map preserved). Images are *visual* members: only an agent with native
vision can read them, and the ledger must say so.

Approach for PDF adapted from QE Engineering's per-page parser (concept; original code).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
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
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 2000
MAX_SHEET_CELLS = 500_000
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_R = "{http://schemas.openxmlformats.org/package/2006/relationships}"


class ExtractionError(ValueError):
    pass


@dataclass
class Extraction:
    text: str
    extractor: str
    encoding: str = "utf-8"
    gaps: list[str] = field(default_factory=list)  # content NOT turned into text
    notes: list[str] = field(
        default_factory=list
    )  # extracted, but with caveats (hidden sheet, merged cells...)
    pages: list[list[int]] = field(default_factory=list)  # [page, line_start, line_end]
    sheets: list[list[object]] = field(default_factory=list)  # [sheet, line_start, line_end]
    visual: bool = False


def extractor_for(name: str) -> str | None:
    lower = PurePosixPath(name.lower())
    if lower.suffix == ".docx":
        return "docx"
    if lower.suffix == ".xlsx":
        return "xlsx"
    if lower.suffix == ".pdf":
        return "pdf"
    if lower.suffix in IMAGE_SUFFIXES:
        return "image"
    if lower.suffix in TEXT_SUFFIXES or lower.name in {"readme", "license", "makefile", "dockerfile"}:
        return "text"
    return None


def decode_text(data: bytes) -> tuple[str, str]:
    """Decode text with BOM detection; fall back to cp1252 only when UTF-8 fails (recorded)."""
    if len(data) > MAX_TEXT_BYTES:
        raise ExtractionError("member exceeds text size limit")
    if data.startswith(b"\xef\xbb\xbf"):
        text, enc = data[3:].decode("utf-8"), "utf-8-sig"
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text, enc = data.decode("utf-16"), "utf-16"
    else:
        try:
            text, enc = data.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            try:
                text, enc = data.decode("cp1252"), "cp1252 (fallback: not valid UTF-8)"
            except UnicodeDecodeError as exc:
                raise ExtractionError("text is neither UTF-8 nor cp1252") from exc
    if "\x00" in text:
        raise ExtractionError("binary content")
    return text.replace("\r\n", "\n").replace("\r", "\n"), enc


def _xml(data: bytes) -> ElementTree.Element:
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise ExtractionError("DTD/entity declarations are not accepted")
    return ElementTree.fromstring(data)  # noqa: S314 - DTD/entities rejected above; sizes bounded


def _read_part(zf: zipfile.ZipFile, name: str) -> bytes:
    info = zf.getinfo(name)
    if info.file_size > MAX_TEXT_BYTES:
        raise ExtractionError(f"{name} exceeds size limit")
    return zf.read(info)


# ----------------------------------------------------------------------------- docx
def _docx_blocks(root: ElementTree.Element, gaps: list[str], label: str) -> list[str]:
    lines: list[str] = []

    def para_text(p: ElementTree.Element) -> str:
        out = []
        for node in p.iter():
            if node.tag == f"{_W}t" and node.text:
                out.append(node.text)
            elif node.tag in (f"{_W}tab",):
                out.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                out.append(" ")
        if p.find(f".//{_W}drawing") is not None or p.find(f".//{_W}pict") is not None:
            gaps.append(f"{label}: embedded image/drawing not interpreted")
            out.append(" [imagem/diagrama não interpretado]")
        return "".join(out)

    def walk(container: ElementTree.Element) -> None:
        for block in list(container):
            if block.tag == f"{_W}p":
                lines.append(para_text(block))
            elif block.tag == f"{_W}tbl":
                for row in block.findall(f"{_W}tr"):
                    cells = []
                    for cell in row.findall(f"{_W}tc"):
                        nested = cell.find(f"{_W}tbl")
                        if nested is not None:
                            gaps.append(f"NOTE {label}: nested table flattened into its cell")
                        cells.append(" ".join(para_text(p).strip() for p in cell.iter(f"{_W}p")).strip())
                    lines.append("| " + " | ".join(cells) + " |")
            elif block.tag == f"{_W}sdt":
                content = block.find(f"{_W}sdtContent")
                if content is not None:
                    walk(content)

    body = root.find(f"{_W}body")
    walk(body if body is not None else root)
    return lines


def _docx(data: bytes) -> Extraction:
    gaps: list[str] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ExtractionError("not a readable .docx package") from exc
    with zf:
        names = set(zf.namelist())
        if "word/document.xml" not in names:
            raise ExtractionError("not a readable .docx package")
        lines = _docx_blocks(_xml(_read_part(zf, "word/document.xml")), gaps, "body")
        extra = sorted(n for n in names if re.fullmatch(r"word/(header|footer)\d*\.xml", n))
        extra += [n for n in ("word/footnotes.xml", "word/endnotes.xml", "word/comments.xml") if n in names]
        for part in extra:
            section = _docx_blocks(_xml(_read_part(zf, part)), gaps, part)
            section = [s for s in section if s.strip()]
            if section:
                lines.append(f"--- {PurePosixPath(part).stem} ---")
                lines.extend(section)
        if any(n.startswith("word/embeddings/") for n in names):
            gaps.append("embedded objects (word/embeddings) not interpreted")
    notes = sorted({g[5:] for g in gaps if g.startswith("NOTE ")})
    real = sorted({g for g in gaps if not g.startswith("NOTE ")})
    return Extraction("\n".join(lines), "docx", gaps=real, notes=notes)


# ----------------------------------------------------------------------------- xlsx
def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref)
    n = 0
    for ch in letters.group(0) if letters else "":
        n = n * 26 + (ord(ch) - 64)
    return n


def _xlsx(data: bytes) -> Extraction:
    gaps: list[str] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ExtractionError("not a readable .xlsx package") from exc
    notes: list[str] = []
    with zf:
        names = set(zf.namelist())
        if "xl/workbook.xml" not in names:
            raise ExtractionError("not a readable .xlsx package")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            for si in _xml(_read_part(zf, "xl/sharedStrings.xml")).findall(f"{_S}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_S}t")))
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for rel in _xml(_read_part(zf, "xl/_rels/workbook.xml.rels")).findall(f"{_PKG_R}Relationship"):
                rels[rel.get("Id")] = rel.get("Target", "")
        workbook = _xml(_read_part(zf, "xl/workbook.xml"))
        lines: list[str] = []
        sheets: list[list[object]] = []
        cells_seen = 0
        for sheet in workbook.iter(f"{_S}sheet"):
            name = sheet.get("name", "?")
            target = rels.get(sheet.get(f"{_R}id"), "")
            part = "xl/" + target.lstrip("/").removeprefix("xl/") if target else ""
            if sheet.get("state") in ("hidden", "veryHidden"):
                notes.append(f"sheet {name!r} is hidden (content included; may be a draft)")
            if part not in names:
                gaps.append(f"sheet {name!r} part not found")
                continue
            root = _xml(_read_part(zf, part))
            start = len(lines) + 1
            lines.append(f"## Planilha: {name}")
            for merge in root.iter(f"{_S}mergeCell"):
                notes.append(f"sheet {name!r}: merged range {merge.get('ref')} (value only in first cell)")
            for row in root.iter(f"{_S}row"):
                values = []
                for c in row.findall(f"{_S}c"):
                    cells_seen += 1
                    if cells_seen > MAX_SHEET_CELLS:
                        raise ExtractionError("spreadsheet exceeds cell limit")
                    kind, v, f = c.get("t"), c.find(f"{_S}v"), c.find(f"{_S}f")
                    if kind == "s" and v is not None and v.text is not None:
                        value = shared[int(v.text)] if int(v.text) < len(shared) else ""
                    elif kind == "inlineStr":
                        value = "".join(t.text or "" for t in c.iter(f"{_S}t"))
                    else:
                        value = v.text if v is not None and v.text is not None else ""
                    if f is not None and f.text:
                        value = f"{value} (fórmula: ={f.text})"
                    if value != "":
                        values.append(f"{c.get('r', '?')}={value}")
                if values:
                    lines.append(f"| {name}!{row.get('r', '?')} | " + " | ".join(values) + " |")
            sheets.append([name, start, len(lines)])
        if any(n.startswith("xl/drawings/") or n.startswith("xl/charts/") for n in names):
            gaps.append("charts/drawings not interpreted")
    return Extraction(
        "\n".join(lines), "xlsx", gaps=sorted(set(gaps)), notes=sorted(set(notes)), sheets=sheets
    )


# ----------------------------------------------------------------------------- pdf
def _pdf(data: bytes) -> Extraction:
    try:
        from pypdf import PdfReader
    except ImportError:
        # Native-first (corrective qualification R6, defect D3): without a text layer on this host the
        # original is still the primary input; it becomes a visual member that only an agent reading
        # the rendered pages natively (with a recorded visual_transcription) can certify as read.
        if not data.startswith(b"%PDF"):
            raise ExtractionError("not a PDF document") from None
        return Extraction(
            "",
            "pdf",
            gaps=[
                "no PDF text layer on this host (optional 'pdf' extra not installed): read the pages natively"
            ],
            visual=True,
        )
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("encrypted PDF")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ExtractionError("PDF exceeds page limit")
        lines: list[str] = []
        pages: list[list[int]] = []
        gaps: list[str] = []
        for number, page in enumerate(reader.pages, start=1):
            start = len(lines) + 1
            lines.append(f"--- página {number} ---")
            try:
                text = page.extract_text(extraction_mode="layout") or ""
            except Exception:
                text = ""
            page_lines = [ln.rstrip() for ln in text.replace("\r", "\n").split("\n")]
            while page_lines and not page_lines[-1].strip():
                page_lines.pop()
            if not any(ln.strip() for ln in page_lines):
                gaps.append(f"page {number}: no extractable text layer (scanned or image)")
            if "/XObject" in str(page.get("/Resources", {})):
                gaps.append(f"page {number}: contains images not interpreted")
            lines.extend(page_lines)
            pages.append([number, start, len(lines)])
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"PDF text extraction failed: {type(exc).__name__}") from exc
    if not any(ln.strip() for ln in lines if not ln.startswith("--- página")):
        # scanned PDF: no text anywhere, so the pages must be read natively (D3)
        return Extraction(
            "", "pdf", gaps=[*gaps, "no extractable text on any page: read the pages natively"], visual=True
        )
    return Extraction("\n".join(lines), "pdf", gaps=gaps, pages=pages)


def extract(name: str, data: bytes) -> Extraction:
    kind = extractor_for(name)
    if kind == "text":
        text, enc = decode_text(data)
        return Extraction(text, "text", encoding=enc)
    if kind == "docx":
        return _docx(data)
    if kind == "xlsx":
        return _xlsx(data)
    if kind == "pdf":
        return _pdf(data)
    if kind == "image":
        return Extraction(
            "", "image", gaps=["visual content: requires agent vision or a transcription"], visual=True
        )
    raise ExtractionError("no text extractor for this format; provide a transcription")


def read_member_bytes(source_path: Path, kind: str, member: str) -> bytes:
    """Read one member of a file, directory or zip/tar archive source."""
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


# ---------------------------------------------------------------------------- native-first policy
#: How each format should be read. The agent reads the ORIGINAL with the host's native tools; the
#: extracted text is a verification layer (quote checks, line locators) and the fallback when the
#: host cannot open the format. ``fallback_complete``: may a member be certified ``read`` from the
#: extracted layer alone? Never for PDF (a text layer drops layout, figures and drawn diagrams) or
#: images; for DOCX/XLSX only when the structural parse reported no gaps, with limitations declared.
READING_POLICY: dict[str, dict[str, Any]] = {
    "text": {
        "native": "open the original file; it is identical to the verification text",
        "extracted_layer": "decoded text, identical to the original",
        "fallback_complete": True,
    },
    "pdf": {
        "native": "open the original PDF with the host's native PDF/vision reader, page by page",
        "extracted_layer": "PDF text layer only: no layout, figures, drawn diagrams or scanned pages",
        "fallback_complete": False,
    },
    "docx": {
        "native": "open the original .docx natively if the host can; otherwise use the structural extraction",
        "extracted_layer": "structural parse of body, tables, headers, footers, notes and comments; "
        "no drawings, images or text boxes",
        "fallback_complete": True,
    },
    "xlsx": {
        "native": "open the original .xlsx natively if the host can; otherwise use the cell extraction",
        "extracted_layer": "cell values and formulas with cached values; no charts, colours or shapes",
        "fallback_complete": True,
    },
    "image": {
        "native": "look at the original image with the host's native vision and transcribe what you see",
        "extracted_layer": "none",
        "fallback_complete": False,
    },
}
READING_METHODS = frozenset({"native", "native_vision", "extracted_text"})
NATIVE_METHODS = frozenset({"native", "native_vision"})
