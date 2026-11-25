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


def _pdf_text(value: str) -> str:
    """Encode text for a WinAnsi (cp1252) Helvetica string literal."""
    out = []
    for byte in value.encode("cp1252"):
        ch = chr(byte)
        if ch in "()\\":
            out.append("\\" + ch)
        elif 32 <= byte < 127:
            out.append(ch)
        else:
            out.append(f"\\{byte:03o}")
    return "".join(out)


def make_pdf(path: Path, pages: list[list[str] | None]) -> None:
    """Minimal PDF with a real text layer. A page given as None contains only vector shapes (no text)."""
    objects: list[bytes] = []
    kids = []
    font_id = 3
    for index, lines in enumerate(pages):
        page_id = 4 + index * 2
        content_id = page_id + 1
        kids.append(f"{page_id} 0 R")
        if lines is None:
            stream = "0.5 g 72 500 300 150 re f 0 g 72 450 m 372 450 l S"
        else:
            ops = ["BT", "/F1 11 Tf", "14 TL", "72 760 Td"]
            for line in lines:
                ops.append(f"({_pdf_text(line)}) Tj T*")
            ops.append("ET")
            stream = "\n".join(ops)
        data = stream.encode("latin-1")
        objects.append(
            (
                f"{page_id} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>\nendobj\n"
            ).encode("latin-1")
        )
        objects.append(
            f"{content_id} 0 obj\n<< /Length {len(data)} >>\nstream\n".encode("latin-1")
            + data
            + b"\nendstream\nendobj\n"
        )
    head = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>\nendobj\n".encode(
            "latin-1"
        ),
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica"
        b" /Encoding /WinAnsiEncoding >>\nendobj\n",
    ]
    body = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = []
    for obj in head + objects:
        offsets.append(len(body))
        body += obj
    xref = len(body)
    body += f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode("latin-1")
    body += b"".join(f"{o:010d} 00000 n \n".encode("latin-1") for o in offsets)
    body += f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode(
        "latin-1"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def make_xlsx(
    path: Path,
    sheets: list[tuple[str, list[list[str]], bool]],
    merges: dict[str, list[str]] | None = None,
    formulas: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> None:
    """XLSX with shared strings (as spreadsheet tools write them), hidden sheets, merges and formulas."""
    shared: list[str] = []

    def sidx(value: str) -> int:
        if value not in shared:
            shared.append(value)
        return shared.index(value)

    def col(n: int) -> str:
        name = ""
        while n:
            n, rem = divmod(n - 1, 26)
            name = chr(65 + rem) + name
        return name

    sheet_xml = []
    for name, rows, _hidden in sheets:
        out = []
        for r, row in enumerate(rows, start=1):
            cells = []
            for c, value in enumerate(row, start=1):
                ref = f"{col(c)}{r}"
                if formulas and (name, ref) in formulas:
                    formula, cached = formulas[(name, ref)]
                    cells.append(f'<c r="{ref}"><f>{escape(formula)}</f><v>{escape(cached)}</v></c>')
                elif value != "":
                    cells.append(f'<c r="{ref}" t="s"><v>{sidx(value)}</v></c>')
            out.append(f'<row r="{r}">{"".join(cells)}</row>')
        merge = ""
        if merges and merges.get(name):
            merge = (
                f'<mergeCells count="{len(merges[name])}">'
                + "".join(f'<mergeCell ref="{m}"/>' for m in merges[name])
                + "</mergeCells>"
            )
        sheet_xml.append(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(out)}</sheetData>{merge}</worksheet>"
        )
    sst = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared)}" '
        f'uniqueCount="{len(shared)}">' + "".join(f"<si><t>{escape(s)}</t></si>" for s in shared) + "</sst>"
    )
    hidden_attr = ' state="hidden"'
    wb_sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"{hidden_attr if hidden else ""}/>'
        for i, (name, _rows, hidden) in enumerate(sheets, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{wb_sheets}</sheets></workbook>"
    )
    rel_base = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="{rel_base}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + f'<Relationship Id="rIdS" Type="{rel_base}/sharedStrings" Target="sharedStrings.xml"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{rel_base}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    ct = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/></Types>'
    )
    parts = [
        ("[Content_Types].xml", ct),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", wb_rels),
        ("xl/sharedStrings.xml", sst),
    ]
    parts += [(f"xl/worksheets/sheet{i}.xml", x) for i, x in enumerate(sheet_xml, start=1)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in parts:
            info = zipfile.ZipInfo(name, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, text.encode("utf-8"))


def make_rich_docx(path: Path) -> None:
    """DOCX with header, footer, footnote, comment, nested table and an embedded drawing."""
    make_docx(path)
    with zipfile.ZipFile(path) as zf:
        parts = {n: zf.read(n) for n in zf.namelist()}
    doc = parts["word/document.xml"].decode("utf-8")
    drawing = '<w:p><w:r><w:drawing><wp:inline xmlns:wp="x"/></w:drawing></w:r></w:p>'
    nested = (
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Externa</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r>"
        "<w:t>Interna</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:tc></w:tr></w:tbl>"
    )
    doc = doc.replace("</w:body>", drawing + nested + "</w:body>")
    parts["word/document.xml"] = doc.encode("utf-8")
    for part, text in (
        ("word/header1.xml", "Cabeçalho: versão 2 (fictício)"),
        ("word/footer1.xml", "Rodapé: documento sintético"),
        ("word/footnotes.xml", "Nota: prazos em dias corridos."),
        ("word/comments.xml", "Comentário: confirmar com a coordenação."),
    ):
        root = (
            "hdr"
            if "header" in part
            else "ftr"
            if "footer" in part
            else ("footnotes" if "foot" in part else "comments")
        )
        parts[part] = (
            f'<?xml version="1.0" encoding="UTF-8"?><w:{root} xmlns:w="{W}">{_para(text)}</w:{root}>'
        ).encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(parts.items()):
            info = zipfile.ZipInfo(name, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)


C11_PAGES: list[list[str] | None] = [
    [
        "PRD - Mutirão de Vacinação de Animais (fictício)",
        "1. O tutor agenda a vacinação informando espécie e idade do animal.",
        "2. Cada horário atende no máximo 10 animais.",
        "3. O voluntário registra a vacina aplicada e o lote.",
        "4. O tutor recebe o comprovante de vacinação.",
    ],
    [
        "Tabela de regras por espécie",
        "Espécie    Idade mínima    Vacina",
        "Cão        3 meses         Antirrábica",
        "Gato       3 meses         Antirrábica",
        "5. Animais abaixo da idade mínima não podem ser agendados.",
    ],
    None,
]
C12_SHEETS: list[tuple[str, list[list[str]], bool]] = [
    (
        "Requisitos",
        [
            ["Empréstimo de salas comunitárias (fictício)", "", ""],
            ["ID", "Requisito", "Prioridade"],
            ["R1", "O morador reserva uma sala informando data, horário e finalidade.", "Alta"],
            ["R2", "Uma reserva dura no máximo o limite da aba Regras.", "Alta"],
            ["R3", "Reservas exigem a antecedência mínima da aba Regras.", "Média"],
            ["R4", "O zelador vê as reservas do dia por sala.", "Média"],
        ],
        False,
    ),
    (
        "Regras",
        [
            ["Regra", "Valor"],
            ["Duração máxima (horas)", "4"],
            ["Antecedência mínima (dias)", "1"],
            ["Salas disponíveis", ""],
        ],
        False,
    ),
    ("Rascunho", [["Duração máxima (horas)", "8"], ["Observação", "rascunho descartado"]], True),
]

if __name__ == "__main__":
    make_docx(ROOT / "c03-tables-annexes" / "sources" / "anexos" / "validacoes.docx")
    make_png(ROOT / "c10-incomplete-source" / "sources" / "fontes" / "fluxo-pedido.png")
    make_pdf(ROOT / "c11-pdf-source" / "sources" / "prd.pdf", C11_PAGES)
    make_xlsx(
        ROOT / "c12-xlsx-source" / "sources" / "requisitos.xlsx",
        C12_SHEETS,
        merges={"Requisitos": ["A1:C1"]},
        formulas={("Regras", "B4"): ("COUNTA(Salas!A:A)", "3")},
    )
    print("ok")
