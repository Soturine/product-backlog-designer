"""Extraction of PDF, XLSX, rich DOCX, images and non-UTF-8 text, and the ledger rules they imply."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from tools.make_binary_fixtures import C11_PAGES, C12_SHEETS, make_pdf, make_png, make_rich_docx, make_xlsx

from pbd.pipeline.extract import ExtractionError, decode_text, extract
from pbd.pipeline.reading import validate_ledger
from pbd.pipeline.run import Run, normalize_request, start

pytest.importorskip("pypdf")


def test_pdf_pages_and_gaps(tmp_path: Path) -> None:
    path = tmp_path / "prd.pdf"
    make_pdf(path, C11_PAGES)
    result = extract("prd.pdf", path.read_bytes())
    assert result.extractor == "pdf"
    assert [p[0] for p in result.pages] == [1, 2, 3]
    lines = result.text.splitlines()
    first = result.pages[0]
    assert any("10 animais" in ln for ln in lines[first[1] - 1 : first[2]])
    assert "Antirrábica" in result.text and "Cão" in result.text  # cp1252 accents preserved
    assert result.gaps == ["page 3: no extractable text layer (scanned or image)"]


def test_pdf_malformed_is_reported_not_guessed() -> None:
    with pytest.raises(ExtractionError, match="PDF"):
        extract("broken.pdf", b"%PDF-1.4 garbage")


def test_xlsx_sheets_cells_formulas_hidden_and_merges(tmp_path: Path) -> None:
    path = tmp_path / "req.xlsx"
    make_xlsx(
        path,
        C12_SHEETS,
        merges={"Requisitos": ["A1:C1"]},
        formulas={("Regras", "B4"): ("COUNTA(Salas!A:A)", "3")},
    )
    result = extract("req.xlsx", path.read_bytes())
    assert [s[0] for s in result.sheets] == ["Requisitos", "Regras", "Rascunho"]
    assert "| Requisitos!3 | A3=R1 | B3=O morador reserva uma sala" in result.text
    assert "B4=3 (fórmula: =COUNTA(Salas!A:A))" in result.text
    assert result.gaps == []  # everything was extracted; caveats are notes, not gaps
    assert any("hidden" in n for n in result.notes) and any("A1:C1" in n for n in result.notes)


def test_rich_docx_headers_footnotes_comments_and_drawings(tmp_path: Path) -> None:
    path = tmp_path / "anexo.docx"
    make_rich_docx(path)
    result = extract("anexo.docx", path.read_bytes())
    for expected in (
        "Cabeçalho: versão 2",
        "Rodapé: documento sintético",
        "Nota: prazos em dias corridos",
        "Comentário: confirmar",
        "| Telefone |",
        "Interna",
    ):
        assert expected in result.text, expected
    assert any("drawing" in g for g in result.gaps) and any("nested table" in n for n in result.notes)


def test_images_are_visual_members(tmp_path: Path) -> None:
    path = tmp_path / "fluxo.png"
    make_png(path)
    result = extract("fluxo.png", path.read_bytes())
    assert result.visual and result.text == "" and result.gaps


@pytest.mark.parametrize(
    ("data", "encoding"),
    [
        ("ação".encode(), "utf-8"),
        (b"\xef\xbb\xbf" + "ação".encode(), "utf-8-sig"),
        ("ação".encode("utf-16"), "utf-16"),
        ("ação".encode("cp1252"), "cp1252 (fallback: not valid UTF-8)"),
    ],
)
def test_text_encodings_are_detected_and_recorded(data: bytes, encoding: str) -> None:
    text, enc = decode_text(data)
    assert text == "ação" and enc == encoding


def test_binary_text_rejected() -> None:
    with pytest.raises(ExtractionError):
        decode_text(b"abc\x00def")


# ---------------------------------------------------------------------- ledger rules
@pytest.fixture
def mixed_run(tmp_path: Path) -> Run:
    ws = tmp_path / "ws"
    (ws / "docs").mkdir(parents=True)
    make_pdf(ws / "docs" / "prd.pdf", C11_PAGES)
    make_png(ws / "docs" / "fluxo.png")
    return start(tmp_path / "out", ws, [("docs", "functional")], normalize_request(synthetic=True))


def _ledger(run: Run, members: list[dict[str, Any]], obligations: list[dict[str, Any]]) -> dict[str, Any]:
    src = run.inventory()["sources"][0]
    return {
        "source_id": src["id"],
        "source_digest": src["digest"],
        "reader": {"agent": "r", "model": "m", "independence": "separate_agent"},
        "members": members,
        "obligations": obligations,
    }


def _meta(run: Run, name: str) -> dict[str, Any]:
    return next(m for m in run.inventory()["sources"][0]["members_text"] if m["path"] == name)


def test_start_records_pages_gaps_visual_and_limitations(mixed_run: Run) -> None:
    pdf, png = _meta(mixed_run, "prd.pdf"), _meta(mixed_run, "fluxo.png")
    assert pdf["readable"] and pdf["pages"][0][0] == 1 and pdf["gaps"] and pdf["original_ref"]
    assert png["visual"] and not png["readable"] and mixed_run.path(png["original_ref"]).is_file()
    assert any("extraction gaps" in lim for lim in mixed_run.state.manifest["limitations"])
    assert mixed_run.state.manifest["status"]["source_coverage"] == "incomplete_reading"


def test_gapped_pdf_cannot_be_read_without_transcription(mixed_run: Run) -> None:
    n = _meta(mixed_run, "prd.pdf")["lines"]
    members = [
        {"path": "prd.pdf", "status": "read", "lines_read": [[1, n]]},
        {"path": "fluxo.png", "status": "unreadable", "reason": "no vision available"},
    ]
    errors = validate_ledger(mixed_run, _ledger(mixed_run, members, []))
    assert any("extraction gaps" in e for e in errors)
    members[0] = {
        "path": "prd.pdf",
        "status": "partial",
        "lines_read": [[1, n]],
        "reason": "page 3 has no text",
    }
    assert validate_ledger(mixed_run, _ledger(mixed_run, members, [])) == []


def test_page_locator_must_contain_cited_lines(mixed_run: Run) -> None:
    pdf = _meta(mixed_run, "prd.pdf")
    n = pdf["lines"]
    members = [
        {"path": "prd.pdf", "status": "partial", "lines_read": [[1, n]], "reason": "page 3 gap"},
        {"path": "fluxo.png", "status": "unreadable", "reason": "no vision"},
    ]
    text = mixed_run.path(pdf["text_ref"]).read_text(encoding="utf-8").splitlines()
    line = next(i for i, t in enumerate(text, start=1) if "10 animais" in t)  # a line on page 1
    good = {
        "key": "R1",
        "text": "limite",
        "category": "constraint",
        "quote": "no máximo 10 animais",
        "locator": {"member": "prd.pdf", "line_start": line, "page": 1},
    }
    assert validate_ledger(mixed_run, _ledger(mixed_run, members, [good])) == []
    bad = {**good, "locator": {**good["locator"], "page": 2}}
    assert any(
        "page 2 does not contain" in e for e in validate_ledger(mixed_run, _ledger(mixed_run, members, [bad]))
    )


def test_visual_member_needs_agent_vision_transcription(mixed_run: Run) -> None:
    n = _meta(mixed_run, "prd.pdf")["lines"]
    pdf = {"path": "prd.pdf", "status": "partial", "lines_read": [[1, n]], "reason": "page 3 gap"}
    no_vt = [pdf, {"path": "fluxo.png", "status": "read"}]
    assert any("agent vision" in e for e in validate_ledger(mixed_run, _ledger(mixed_run, no_vt, [])))
    vt = {"method": "agent_vision", "model": "test-vision-model", "text": "Caixa A seta para Caixa B"}
    with_vt = [pdf, {"path": "fluxo.png", "status": "read", "visual_transcription": vt}]
    ob = {
        "key": "V1",
        "text": "fluxo A para B",
        "category": "functional",
        "quote": "Caixa A seta",
        "locator": {"member": "fluxo.png", "line_start": 1, "anchor": "diagrama"},
    }
    assert validate_ledger(mixed_run, _ledger(mixed_run, with_vt, [ob])) == []
    fake = {**ob, "quote": "Caixa C"}
    assert any(
        "visual_transcription" in e for e in validate_ledger(mixed_run, _ledger(mixed_run, with_vt, [fake]))
    )
    bad_vt = [pdf, {"path": "fluxo.png", "status": "read", "visual_transcription": {"text": "x"}}]
    assert any("agent_vision" in e for e in validate_ledger(mixed_run, _ledger(mixed_run, bad_vt, [])))
