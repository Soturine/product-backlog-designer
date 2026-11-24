from __future__ import annotations

import copy
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.reading import submit_ledger, validate_ledger
from pbd.pipeline.run import Run, RunError, normalize_request, start
from pbd.validation.schema import validate

PRD = """# PRD fictício — Horta comunitária

## 2. Reservas
2.1 Um membro pode reservar um canteiro livre para uma temporada.
2.2 Um canteiro já reservado na mesma temporada não aceita nova reserva.

## 3. Fora do escopo
Pagamentos não fazem parte desta versão.
"""


def _docx(path: Path, paragraphs: list[str], rows: list[list[str]]) -> None:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    table = "".join(
        "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row) + "</w:tr>"
        for row in rows
    )
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{w}">'
        f"<w:body>{body}<w:tbl>{table}</w:tbl></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "anexos").mkdir(parents=True)
    (ws / "prd.md").write_text(PRD, encoding="utf-8")
    _docx(
        ws / "anexos" / "regras.docx", ["Regras de temporada"], [["Regra", "Valor"], ["Duração", "6 meses"]]
    )
    (ws / "anexos" / "diagrama.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    return ws


@pytest.fixture
def run(tmp_path: Path, workspace: Path) -> Run:
    req = normalize_request(language="pt-BR", synthetic=True)
    return start(tmp_path / "out", workspace, [("prd.md", "functional"), ("anexos", "functional")], req)


def _ledger(run: Run, selector: str) -> dict[str, Any]:
    src = next(s for s in run.inventory()["sources"] if s["selector"] == selector)
    return {
        "source_id": src["id"],
        "source_digest": src["digest"],
        "reader": {"agent": "reader-a", "model": "test-model", "independence": "separate_agent"},
        "members": [],
        "obligations": [],
    }


def _prd_ledger(run: Run) -> dict[str, Any]:
    led = _ledger(run, "prd.md")
    led["members"] = [{"path": "prd.md", "status": "read", "lines_read": [[1, 9]]}]
    led["obligations"] = [
        {
            "key": "R1",
            "text": "Membro reserva canteiro livre por temporada",
            "category": "functional",
            "locator": {"member": "prd.md", "line_start": 4, "section": "2.1"},
            "quote": "Um membro pode reservar um canteiro livre",
        },
        {
            "key": "R2",
            "text": "Canteiro reservado não aceita nova reserva na temporada",
            "category": "error",
            "locator": {"member": "prd.md", "line_start": 5},
            "quote": "não aceita nova reserva",
        },
    ]
    led["exclusions"] = [
        {
            "text": "Pagamentos fora do escopo",
            "locator": {"member": "prd.md", "line_start": 8},
            "quote": "Pagamentos não fazem parte",
        }
    ]
    return led


def test_start_inventories_extracts_and_assigns_one_reader_per_source(run: Run) -> None:
    order = json.loads(run.path("work-order.json").read_text(encoding="utf-8"))
    assert order["next_stage"] == "reading"
    assigns = order["reader_assignments"]
    assert [a["selector"] for a in assigns] == ["prd.md", "anexos"]  # directory = one logical source
    anexos = {m["path"]: m for m in assigns[1]["members"]}
    assert anexos["regras.docx"]["readable"] and anexos["regras.docx"]["lines"] == 3
    assert not anexos["diagrama.png"]["readable"] and "transcription" in anexos["diagrama.png"]["reason"]
    docx_text = run.path(anexos["regras.docx"]["text_ref"]).read_text(encoding="utf-8")
    assert "| Duração | 6 meses |" in docx_text
    assert validate("run-manifest", run.state.manifest) == []
    assert run.state.manifest["status"]["source_coverage"] == "incomplete_reading"
    assert any("diagrama.png" in lim for lim in run.state.manifest["limitations"])
    assert run.stage_status("inventory") == "complete"


def test_valid_ledgers_complete_reading(run: Run) -> None:
    out = submit_ledger(run, _prd_ledger(run))
    assert out["pending_sources"] and run.stage_status("reading") == "pending"
    led = _ledger(run, "anexos")
    led["members"] = [
        {"path": "regras.docx", "status": "read", "lines_read": [[1, 3]]},
        {"path": "diagrama.png", "status": "unreadable", "reason": "image without transcription"},
    ]
    led["obligations"] = [
        {
            "key": "T1",
            "text": "Temporada dura 6 meses",
            "category": "constraint",
            "locator": {"member": "regras.docx", "line_start": 3, "table": "Regras"},
            "quote": "Duração | 6 meses",
        }
    ]
    submit_ledger(run, led)
    assert run.stage_status("reading") == "complete"
    assert run.state.manifest["status"]["source_coverage"] == "incomplete_reading"  # png never read
    order = json.loads(run.path("work-order.json").read_text(encoding="utf-8"))
    assert order["next_stage"] == "claims"
    assert {k["ref"].split(":")[1] for k in order["reader_obligation_keys"]} == {"R1", "R2", "T1"}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda led: led["obligations"][0].update(quote="Um membro pode reservar dois canteiros"),
            "quote not found",
        ),
        (lambda led: led["obligations"][0]["locator"].update(line_start=40), "outside"),
        (lambda led: led["members"][0].update(lines_read=[[1, 5]]), "every line"),
        (lambda led: led["members"].clear(), "not accounted"),
        (lambda led: led.update(source_digest="sha256:" + "0" * 64), "digest"),
        (lambda led: led.update(stories=[{"title": "x"}]), "design/coverage decisions"),
        (lambda led: led["reader"].pop("model"), "model"),
        (lambda led: led["obligations"][1].update(key="R1"), "duplicate key"),
        (lambda led: led["obligations"][0].update(category="wish"), "category"),
        (lambda led: led["members"][0].update(status="partial", lines_read=[[1, 3]]), "requires a reason"),
    ],
)
def test_invalid_ledgers_rejected_atomically(run: Run, mutate: Any, message: str) -> None:
    led = _prd_ledger(run)
    mutate(led)
    before = copy.deepcopy(run.state.manifest)
    with pytest.raises(RunError) as exc:
        submit_ledger(run, led)
    assert any(message in e for e in exc.value.errors), exc.value.errors
    assert not run.path(f"stages/reading/{led['source_id']}.json").exists()
    assert run.state.manifest == before


def test_partial_read_cannot_cite_unread_lines(run: Run) -> None:
    led = _prd_ledger(run)
    led["members"] = [
        {"path": "prd.md", "status": "partial", "lines_read": [[1, 4]], "reason": "context limit"}
    ]
    errors = validate_ledger(run, led)
    assert any("did not report as read" in e for e in errors)


def test_unreadable_member_cannot_be_claimed_read(run: Run) -> None:
    led = _ledger(run, "anexos")
    led["members"] = [
        {"path": "regras.docx", "status": "read", "lines_read": [[1, 3]]},
        {"path": "diagrama.png", "status": "read", "lines_read": [[1, 1]]},
    ]
    assert any("no extractable text" in e for e in validate_ledger(run, led))


def test_reading_closed_after_completion(run: Run) -> None:
    submit_ledger(run, _prd_ledger(run))
    led = _ledger(run, "anexos")
    led["members"] = [
        {"path": "regras.docx", "status": "read", "lines_read": [[1, 3]]},
        {"path": "diagrama.png", "status": "unreadable", "reason": "image"},
    ]
    submit_ledger(run, led)
    with pytest.raises(RunError, match="complete"):
        submit_ledger(run, _prd_ledger(run))


def test_start_requires_sources_and_valid_request(tmp_path: Path, workspace: Path) -> None:
    with pytest.raises(RunError):
        start(tmp_path / "o", workspace, [], normalize_request())
    with pytest.raises(RunError):
        normalize_request(levels=["sagas"])
    with pytest.raises(RunError):
        normalize_request(formats=["pdf"])
    req = normalize_request(levels=["stories", "acceptance"], formats=["csv"])
    assert req["omitted_levels"] == ["epics", "features", "tasks", "dependencies"]
    assert req["formats"] == ["csv", "html", "json"]


def test_run_reload_from_disk(run: Run, tmp_path: Path) -> None:
    again = Run.load(tmp_path / "out")
    assert again.run_id == run.run_id and again.stage_status("inventory") == "complete"
