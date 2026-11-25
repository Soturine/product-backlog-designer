"""Synthetic run builder used by pipeline tests (fictional community-garden domain)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pbd.pipeline.design import submit_claims, submit_design
from pbd.pipeline.reading import submit_ledger
from pbd.pipeline.run import Run, normalize_request, start

PRD = """# PRD fictício — Horta comunitária

## 2. Reservas
2.1 Um membro pode reservar um canteiro livre para uma temporada.
2.2 Um canteiro já reservado na mesma temporada não aceita nova reserva.
2.3 A reserva aparece na lista "Minhas reservas" do membro.
2.4 Reservas são aprovadas manualmente pela coordenação.

## 3. Fora do escopo
Pagamentos não fazem parte desta versão.
"""
ADR = """# ADR-001 — Confirmação automática
Status: aprovado
Decisão: reservas válidas são confirmadas automaticamente, sem aprovação manual.
"""


def make_workspace(root: Path) -> Path:
    ws = root / "ws"
    (ws / "decisoes").mkdir(parents=True)
    (ws / "prd.md").write_text(PRD, encoding="utf-8")
    (ws / "decisoes" / "adr-001.md").write_text(ADR, encoding="utf-8")
    return ws


def ledger(
    run: Run,
    selector: str,
    members: list[dict[str, Any]],
    obligations: list[dict[str, Any]],
    agent: str = "reader",
) -> dict[str, Any]:
    src = next(s for s in run.inventory()["sources"] if s["selector"] == selector)
    members = [with_reading(m) for m in members]
    return {
        "source_id": src["id"],
        "source_digest": src["digest"],
        "reader": {"agent": agent, "model": "test-model", "independence": "separate_agent"},
        "members": members,
        "obligations": obligations,
    }


def with_reading(member: dict[str, Any]) -> dict[str, Any]:
    """Default native-first reading declaration (tests that probe the rules set their own)."""
    if "reading" in member or member.get("status") not in ("read", "partial"):
        return member
    path = str(member["path"]).lower()
    if path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        reading = {"method": "native_vision", "tool": "host image viewer", "limitations": []}
    elif path.endswith(".pdf"):
        reading = {"method": "native", "tool": "host PDF reader", "limitations": []}
    else:
        reading = {"method": "native", "tool": "host file reader", "limitations": []}
    return {**member, "reading": reading}


def rd(path: str) -> dict[str, Any]:
    """The default reading declaration for a member path (spread into hand-written member dicts)."""
    return {"reading": with_reading({"path": path, "status": "read"})["reading"]}


def src_id(run: Run, selector: str) -> str:
    return str(next(s["id"] for s in run.inventory()["sources"] if s["selector"] == selector))


def read_all(run: Run) -> None:
    submit_ledger(
        run,
        ledger(
            run,
            "prd.md",
            [{"path": "prd.md", "status": "read", "lines_read": [[1, 10]]}],
            [
                {
                    "key": "R1",
                    "text": "Reservar canteiro livre",
                    "category": "functional",
                    "locator": {"member": "prd.md", "line_start": 4},
                    "quote": "pode reservar um canteiro livre",
                },
                {
                    "key": "R2",
                    "text": "Rejeitar canteiro já reservado",
                    "category": "error",
                    "locator": {"member": "prd.md", "line_start": 5},
                    "quote": "não aceita nova reserva",
                },
                {
                    "key": "R3",
                    "text": "Reserva listada para o membro",
                    "category": "functional",
                    "locator": {"member": "prd.md", "line_start": 6},
                    "quote": "Minhas reservas",
                },
                {
                    "key": "R4",
                    "text": "Aprovação manual",
                    "category": "functional",
                    "locator": {"member": "prd.md", "line_start": 7},
                    "quote": "aprovadas manualmente",
                },
                {
                    "key": "X1",
                    "text": "Pagamentos fora do escopo",
                    "category": "out_of_scope",
                    "locator": {"member": "prd.md", "line_start": 10},
                    "quote": "Pagamentos não fazem parte",
                },
            ],
            agent="reader-prd",
        ),
    )
    submit_ledger(
        run,
        ledger(
            run,
            "decisoes",
            [{"path": "adr-001.md", "status": "read", "lines_read": [[1, 3]]}],
            [
                {
                    "key": "D1",
                    "text": "Confirmação automática aprovada",
                    "category": "functional",
                    "locator": {"member": "adr-001.md", "line_start": 2, "line_end": 3},
                    "quote": "Status: aprovado Decisão: reservas válidas são confirmadas automaticamente",
                },
            ],
            agent="reader-adr",
        ),
    )


def claims_payload(run: Run) -> dict[str, Any]:
    p, d = src_id(run, "prd.md"), src_id(run, "decisoes")
    return {
        "orchestrator": {"agent": "orchestrator", "model": "test-model"},
        "claims": [
            {
                "key": "C1",
                "text": "Um membro pode reservar um canteiro livre para uma temporada.",
                "category": "functional",
                "sources": [f"{p}:R1"],
            },
            {
                "key": "C2",
                "text": "Canteiro reservado na temporada rejeita nova reserva.",
                "category": "error",
                "sources": [f"{p}:R2"],
            },
            {
                "key": "C3",
                "text": "A reserva aparece em Minhas reservas.",
                "category": "functional",
                "sources": [f"{p}:R3"],
            },
            {
                "key": "C4",
                "text": "Reservas aprovadas manualmente.",
                "category": "functional",
                "sources": [f"{p}:R4"],
            },
            {
                "key": "C5",
                "text": "Confirmar automaticamente reservas válidas.",
                "category": "functional",
                "sources": [f"{d}:D1"],
            },
            {
                "key": "C6",
                "text": "Pagamentos estão fora do escopo.",
                "category": "out_of_scope",
                "sources": [f"{p}:X1"],
            },
        ],
        "decisions": [
            {
                "key": "DEC1",
                "text": "Confirmação automática substitui aprovação manual.",
                "status": "approved",
                "supersedes": ["C4"],
                "sources": [f"{d}:D1"],
            }
        ],
    }


def design_payload() -> dict[str, Any]:
    return {
        "designer": {"agent": "designer", "model": "test-model", "independence": "separate_agent"},
        "items": [
            {
                "key": "E1",
                "type": "epic",
                "title": "Reserva de canteiros",
                "parent": None,
                "claims": ["C1", "C2", "C3"],
                "content": {
                    "kind": "epic",
                    "objective": "Organizar o uso dos canteiros por temporada.",
                    "out_scope": ["Pagamentos"],
                },
            },
            {
                "key": "F1",
                "type": "feature",
                "title": "Reservar canteiro por temporada",
                "parent": "E1",
                "claims": ["C1", "C2", "C3", "C5"],
                "content": {"kind": "feature", "capability": "Membros reservam canteiros livres."},
            },
            {
                "key": "US1",
                "type": "story",
                "title": "Reservar um canteiro livre",
                "parent": "F1",
                "claims": ["C1", "C2", "C5"],
                "acceptance_style": "gherkin",
                "content": {
                    "kind": "role_goal_benefit",
                    "actor": "membro",
                    "want": "o sistema reservasse um canteiro livre",
                    "benefit": "cultivar durante a temporada",
                },
                "fields": {
                    "story_points": {
                        "state": "proposed",
                        "value": 3,
                        "scale": "fibonacci",
                        "rationale": "Proposta; estimativa pertence ao time.",
                    }
                },
            },
            {
                "key": "US2",
                "type": "story",
                "title": "Consultar minhas reservas",
                "parent": "F1",
                "claims": ["C3"],
                "content": {
                    "kind": "role_goal_benefit",
                    "actor": "membro",
                    "want": "ver minhas reservas",
                    "benefit": "acompanhar a temporada",
                },
            },
            {
                "key": "T1",
                "type": "task",
                "title": "Implementar verificação de disponibilidade",
                "parent": "US1",
                "claims": ["C2"],
                "content": {
                    "kind": "task",
                    "summary": "Validar se o canteiro está livre.",
                    "verification": "Teste com canteiro ocupado.",
                },
            },
        ],
        "criteria": [
            {
                "key": "AC1",
                "parent": "US1",
                "condition": "um canteiro livre na temporada",
                "trigger": "o membro solicita a reserva",
                "expected_outcomes": ["a reserva é registrada"],
                "claims": ["C1"],
            },
            {
                "key": "AC2",
                "parent": "US1",
                "condition": "um canteiro já reservado na temporada",
                "trigger": "outro membro solicita a reserva",
                "expected_outcomes": ["nenhuma nova reserva é criada"],
                "claims": ["C2"],
            },
            {
                "key": "AC3",
                "parent": "US1",
                "text": "Uma reserva válida é confirmada automaticamente.",
                "expected_outcomes": ["reserva confirmada sem aprovação manual"],
                "claims": ["C5"],
            },
            {
                "key": "AC4",
                "parent": "US2",
                "text": "A reserva registrada aparece em Minhas reservas.",
                "expected_outcomes": ["reserva listada"],
                "claims": ["C3"],
            },
        ],
        "relations": [],
        "questions": [
            {
                "key": "Q1",
                "text": "Por quanto tempo uma temporada dura?",
                "impact": "Limites da reserva.",
                "affects": ["US1"],
            }
        ],
        "dispositions": [
            {"claim": "C1", "status": "COVERED", "covered_by": ["US1", "AC1"], "rationale": "AC1"},
            {"claim": "C2", "status": "COVERED", "covered_by": ["AC2", "T1"], "rationale": "AC2 e T1"},
            {"claim": "C3", "status": "COVERED", "covered_by": ["US2", "AC4"], "rationale": "AC4"},
            {"claim": "C5", "status": "COVERED", "covered_by": ["AC3"], "rationale": "AC3"},
            {"claim": "C6", "status": "OUT_OF_SCOPE", "rationale": "Exclusão explícita da fonte."},
        ],
    }


def designed_run(tmp: Path, **request: Any) -> Run:
    ws = make_workspace(tmp)
    req = normalize_request(synthetic=True, **request)
    run = start(tmp / "out", ws, [("prd.md", "functional"), ("decisoes", "decision")], req)
    read_all(run)
    submit_claims(run, claims_payload(run))
    submit_design(run, design_payload())
    return run
