"""Regenerate the synthetic binary benchmark sources deterministically (docx annex, png diagram).

Usage: python tools/make_binary_fixtures.py
"""

from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "cases"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
STAMP = (2026, 1, 1, 0, 0, 0)


def _para(text: str) -> str:
    return f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def _table(rows: list[list[str]]) -> str:
    body = "".join("<w:tr>" + "".join(f"<w:tc>{_para(c)}</w:tc>" for c in row) + "</w:tr>" for row in rows)
    return f"<w:tbl>{body}</w:tbl>"


def make_docx(path: Path) -> None:
    body = (
        _para("Anexo A — Regras de validação do cadastro (fictício)")
        + _table(
            [
                ["Campo", "Regra"],
                ["Nome", "Obrigatório; entre 3 e 80 caracteres."],
                ["E-mail", "Obrigatório; formato válido; não pode repetir um e-mail já cadastrado."],
                ["Telefone", "Opcional; somente dígitos; 10 ou 11 dígitos quando informado."],
            ]
        )
        + _para("Cadastros pendentes há mais de 30 dias são arquivados automaticamente.")
    )
    document = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}">'
        f"<w:body>{body}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.wordprocessingml.document.main+xml"/></Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="word/document.xml"/></Relationships>'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in (
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", rels),
            ("word/document.xml", document),
        ):
            info = zipfile.ZipInfo(name, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, text.encode("utf-8"))


def make_png(path: Path, width: int = 64, height: int = 32) -> None:
    """A tiny diagram-like PNG (boxes and an arrow); content cannot be extracted as text."""
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            box = (4 <= x <= 22 or 40 <= x <= 58) and (8 <= y <= 22)
            arrow = 23 <= x <= 39 and y == 15
            row += bytes(
                (40, 40, 40) if (box and (x in (4, 22, 40, 58) or y in (8, 22))) or arrow else (250, 250, 250)
            )
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


if __name__ == "__main__":
    make_docx(ROOT / "c03-tables-annexes" / "sources" / "anexos" / "validacoes.docx")
    make_png(ROOT / "c10-incomplete-source" / "sources" / "fontes" / "fluxo-pedido.png")
    print("ok")
