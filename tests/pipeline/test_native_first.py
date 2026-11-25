"""Native-first reading: originals are the primary input, extraction verifies or falls back."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from tools.make_binary_fixtures import C11_PAGES, make_pdf, make_png, make_rich_docx

from pbd.pipeline.extract import READING_POLICY
from pbd.pipeline.reading import validate_ledger
from pbd.pipeline.run import Run, normalize_request, start


@pytest.fixture
def run(tmp_path: Path) -> Run:
    ws = tmp_path / "ws"
    (ws / "docs").mkdir(parents=True)
    make_pdf(ws / "docs" / "prd.pdf", C11_PAGES)
    make_png(ws / "docs" / "fluxo.png")
    make_rich_docx(ws / "docs" / "regras.docx")
    (ws / "docs" / "notas.md").write_text("# Notas\nUm membro reserva um canteiro.\n", encoding="utf-8")
    return start(tmp_path / "out", ws, [("docs", "functional")], normalize_request(synthetic=True))


def _meta(run: Run, name: str) -> dict[str, Any]:
    return next(m for m in run.inventory()["sources"][0]["members_text"] if m["path"] == name)


def _ledger(
    run: Run, members: list[dict[str, Any]], obligations: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    src = run.inventory()["sources"][0]
    return {
        "source_id": src["id"],
        "source_digest": src["digest"],
        "reader": {"agent": "r", "model": "m", "independence": "separate_agent"},
        "members": members,
        "obligations": obligations or [],
    }


def _member(run: Run, name: str, method: str | None, status: str = "read", **extra: Any) -> dict[str, Any]:
    meta = _meta(run, name)
    entry: dict[str, Any] = {"path": name, "status": status}
    if meta.get("readable"):
        entry["lines_read"] = [[1, meta["lines"]]]
    if method:
        entry["reading"] = {
            "method": method,
            "tool": "host reader",
            "limitations": extra.pop("limitations", []),
        }
    if status != "read":
        entry["reason"] = "declared limitation"
    entry.update(extra)
    return entry


def _rest(run: Run, skip: str) -> list[dict[str, Any]]:
    return [
        {"path": m["path"], "status": "skipped", "reason": "not under test"}
        for m in run.inventory()["sources"][0]["members_text"]
        if m["path"] != skip
    ]


def test_every_member_keeps_its_original_and_policy(run: Run) -> None:
    for name, fmt in (
        ("notas.md", "text"),
        ("prd.pdf", "pdf"),
        ("regras.docx", "docx"),
        ("fluxo.png", "image"),
    ):
        meta = _meta(run, name)
        assert meta["format"] == fmt and run.path(meta["original_ref"]).is_file()
        assert meta["native_reading"] == READING_POLICY[fmt]["native"]
    order = run.write_work_order()
    assert "Native-first" in order["instruction"] and "original_ref" in order["instruction"]
    assert all("extracted_layer" in m for a in order["reader_assignments"] for m in a["members"])


def test_reading_declaration_is_required(run: Run) -> None:
    errors = validate_ledger(run, _ledger(run, [_member(run, "notas.md", None), *_rest(run, "notas.md")]))
    assert any("declare how it was read" in e for e in errors)


def test_pdf_text_layer_alone_never_counts_as_read(run: Run) -> None:
    errors = validate_ledger(
        run, _ledger(run, [_member(run, "prd.pdf", "extracted_text"), *_rest(run, "prd.pdf")])
    )
    assert any("not completely read from its extracted text" in e for e in errors)
    partial = _member(
        run, "prd.pdf", "extracted_text", status="partial", limitations=["host has no PDF reader"]
    )
    assert validate_ledger(run, _ledger(run, [partial, *_rest(run, "prd.pdf")])) == []


def test_structural_fallback_must_declare_limitations(run: Run) -> None:
    bare = _member(run, "regras.docx", "extracted_text")
    errors = validate_ledger(run, _ledger(run, [bare, *_rest(run, "regras.docx")]))
    if _meta(run, "regras.docx").get("gaps"):
        assert any("extraction gaps" in e or "declare its limitations" in e for e in errors)
    else:
        assert any("declare its limitations" in e for e in errors)
        ok = _member(run, "regras.docx", "extracted_text", limitations=["no native .docx reader on host"])
        assert validate_ledger(run, _ledger(run, [ok, *_rest(run, "regras.docx")])) == []


def test_plain_text_may_be_read_from_the_verification_layer(run: Run) -> None:
    m = _member(run, "notas.md", "extracted_text")
    assert validate_ledger(run, _ledger(run, [m, *_rest(run, "notas.md")])) == []


def test_images_need_native_vision(run: Run) -> None:
    vt = {"method": "agent_vision", "model": "m", "text": "Fluxo: pedido aprovado vai para entrega"}
    wrong = _member(run, "fluxo.png", "native", visual_transcription=vt)
    errors = validate_ledger(run, _ledger(run, [wrong, *_rest(run, "fluxo.png")]))
    assert any("native_vision only" in e for e in errors)
    right = _member(run, "fluxo.png", "native_vision", visual_transcription=vt)
    assert validate_ledger(run, _ledger(run, [right, *_rest(run, "fluxo.png")])) == []


def test_transcribed_quotes_without_lines_are_accepted_and_classified(run: Run) -> None:
    from pbd.pipeline.reading import quote_verification

    n = _meta(run, "prd.pdf")["lines"]
    vt = {
        "method": "agent_vision",
        "model": "m",
        "text": "Página 3 (figura): limite de 5 reservas por membro",
    }
    pdf = {
        "path": "prd.pdf",
        "status": "read",
        "lines_read": [[1, n]],
        "visual_transcription": vt,
        "reading": {"method": "native", "tool": "host PDF reader", "limitations": []},
    }
    ob = {
        "key": "R1",
        "text": "limite de reservas",
        "category": "constraint",
        "locator": {"member": "prd.pdf", "page": 3},
        "quote": "limite de 5 reservas por membro",
    }
    assert validate_ledger(run, _ledger(run, [pdf, *_rest(run, "prd.pdf")], [ob])) == []
    bad = {**ob, "quote": "limite de 9 reservas"}
    errors = validate_ledger(run, _ledger(run, [pdf, *_rest(run, "prd.pdf")], [bad]))
    assert any("visual_transcription" in e for e in errors)
    src = run.inventory()["sources"][0]["id"]
    assert quote_verification(run, src, pdf, ob["locator"], ob["quote"]) == "agent_transcription"
    page1 = next(p for p in _meta(run, "prd.pdf")["pages"] if p[0] == 1)
    lines = run.path(_meta(run, "prd.pdf")["text_ref"]).read_text(encoding="utf-8").splitlines()
    quote = lines[page1[1]][:20] if len(lines) > page1[1] and len(lines[page1[1]]) >= 3 else lines[0][:20]
    loc = {"member": "prd.pdf", "line_start": 1, "line_end": n}
    assert quote_verification(run, src, pdf, loc, quote) == "mechanical"
