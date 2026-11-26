"""Second synthetic domain (fictional neighbourhood library, pt-BR) with a blocking question.

Exercises readiness end to end: an open blocking question (the kiosk card-reader model is not
chosen) blocks the driver task only; a mock-contract task and a bounded spike stay actionable and
say why; the kiosk story is partial; an unrelated non-blocking question (what "rápido" means for the
due-date notice) blocks nothing. Payloads stand in for agent outputs in deterministic tests and in
the example report; they are fixture reproductions, never presented as an agent-led run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pbd.pipeline.design import submit_claims, submit_design
from pbd.pipeline.reading import submit_ledger
from pbd.pipeline.run import Run, normalize_request, start
from tests.pipeline.helpers import ledger, src_id

PRD = """# PRD fictício — Biblioteca do bairro

## 1. Empréstimos
1.1 Um leitor cadastrado pode emprestar até 3 livros ao mesmo tempo.
1.2 O prazo de empréstimo é de 14 dias.
1.3 O leitor pode renovar um empréstimo uma vez, se ninguém reservou o livro.
1.4 O leitor vê seus empréstimos e as datas de devolução.
## 2. Quiosque de autoatendimento
2.1 O empréstimo também pode ser feito no quiosque, lendo o cartão do leitor.
2.2 O modelo do leitor de cartões do quiosque ainda não foi escolhido.
## 3. Avisos
3.1 O leitor recebe um aviso rápido antes do vencimento.
## 4. Fora do escopo
Multas por atraso não fazem parte desta versão.
"""

OBLIGATIONS = [
    ("R1", "Limite de 3 empréstimos simultâneos", "functional", 4, "até 3 livros ao mesmo tempo"),
    ("R2", "Prazo de 14 dias", "functional", 5, "prazo de empréstimo é de 14 dias"),
    ("R3", "Renovação única sem reserva", "functional", 6, "renovar um empréstimo uma vez"),
    ("R4", "Lista de empréstimos com datas", "functional", 7, "vê seus empréstimos e as datas de devolução"),
    ("K1", "Empréstimo no quiosque com cartão", "functional", 9, "lendo o cartão do leitor"),
    ("K2", "Modelo do leitor de cartões indefinido", "integration", 10, "ainda não foi escolhido"),
    ("A1", "Aviso rápido antes do vencimento", "functional", 12, "aviso rápido antes do vencimento"),
    ("X1", "Multas fora do escopo", "out_of_scope", 14, "Multas por atraso não fazem parte"),
]


def make_workspace(root: Path) -> Path:
    ws = root / "ws"
    ws.mkdir(parents=True)
    (ws / "prd.md").write_text(PRD, encoding="utf-8")
    return ws


def read_all(run: Run) -> None:
    submit_ledger(
        run,
        ledger(
            run,
            "prd.md",
            [{"path": "prd.md", "status": "read", "lines_read": [[1, 14]]}],
            [
                {
                    "key": k,
                    "text": t,
                    "category": c,
                    "locator": {"member": "prd.md", "line_start": n},
                    "quote": q,
                }
                for k, t, c, n, q in OBLIGATIONS
            ],
            agent="reader-prd",
        ),
    )


def claims_payload(run: Run) -> dict[str, Any]:
    p = src_id(run, "prd.md")

    def claim(
        key: str, text: str, ref: str, category: str = "functional", level: str = "confirmed"
    ) -> dict[str, Any]:
        return {
            "key": key,
            "text": text,
            "category": category,
            "sources": [f"{p}:{ref}"],
            "uncertainty": level,
        }

    return {
        "orchestrator": {"agent": "orchestrator", "model": "test-model"},
        "claims": [
            claim("C1", "Um leitor pode ter até 3 empréstimos ativos.", "R1"),
            claim("C2", "O prazo de empréstimo é de 14 dias.", "R2"),
            claim("C3", "Um empréstimo pode ser renovado uma vez se o livro não estiver reservado.", "R3"),
            claim("C4", "O leitor vê seus empréstimos e as datas de devolução.", "R4"),
            claim("C5", "O empréstimo pode ser feito no quiosque com a leitura do cartão do leitor.", "K1"),
            claim(
                "C6",
                "O modelo do leitor de cartões do quiosque não foi escolhido.",
                "K2",
                "integration",
                "unknown",
            ),
            claim("C7", "O leitor recebe um aviso rápido antes do vencimento.", "A1", level="ambiguous"),
            claim("C8", "Multas por atraso estão fora do escopo.", "X1", "out_of_scope"),
        ],
        "decisions": [],
    }


def _sp(value: int) -> dict[str, Any]:
    return {
        "story_points": {
            "state": "proposed",
            "value": value,
            "scale": "fibonacci",
            "rationale": "Proposta; o time estima.",
        }
    }


def _ready(why: str) -> dict[str, Any]:
    return {"status": "ready", "rationale": why}


def design_payload() -> dict[str, Any]:
    def story(
        key: str,
        parent: str,
        title: str,
        claims: list[str],
        want: str,
        benefit: str,
        sp: int,
        readiness: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "key": key,
            "type": "story",
            "parent": parent,
            "title": title,
            "claims": claims,
            "content": {"kind": "role_goal_benefit", "actor": "leitor", "want": want, "benefit": benefit},
            "fields": _sp(sp),
            "readiness": readiness,
        }

    def task(
        key: str,
        parent: str,
        title: str,
        claims: list[str],
        summary: str,
        check: str,
        readiness: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "key": key,
            "type": "task",
            "parent": parent,
            "title": title,
            "claims": claims,
            "content": {"kind": "task", "summary": summary, "verification": check},
            "readiness": readiness,
        }

    return {
        "designer": {"agent": "designer", "model": "test-model", "independence": "separate_agent"},
        "items": [
            {
                "key": "E1",
                "type": "epic",
                "title": "Empréstimos da biblioteca do bairro",
                "parent": None,
                "claims": ["C1", "C2", "C3", "C4", "C5", "C6", "C7"],
                "content": {
                    "kind": "epic",
                    "objective": "Leitores emprestam, renovam e acompanham livros.",
                    "out_scope": ["Multas por atraso"],
                },
            },
            {
                "key": "F1",
                "type": "feature",
                "parent": "E1",
                "title": "Empréstimo e renovação",
                "claims": ["C1", "C2", "C3", "C4"],
                "content": {
                    "kind": "feature",
                    "capability": "Emprestar, renovar e consultar empréstimos no balcão.",
                },
            },
            {
                "key": "F2",
                "type": "feature",
                "parent": "E1",
                "title": "Quiosque de autoatendimento",
                "claims": ["C5", "C6"],
                "content": {
                    "kind": "feature",
                    "capability": "Emprestar sem atendente, lendo o cartão do leitor.",
                },
            },
            {
                "key": "F3",
                "type": "feature",
                "parent": "E1",
                "title": "Avisos de vencimento",
                "claims": ["C7"],
                "content": {"kind": "feature", "capability": "Avisar o leitor antes do vencimento."},
            },
            story(
                "US1",
                "F1",
                "Emprestar livros no balcão",
                ["C1", "C2"],
                "o sistema registrasse o empréstimo com a data de devolução",
                "levar os livros para casa",
                3,
                _ready("Limite e prazo estão definidos pela fonte."),
            ),
            story(
                "US2",
                "F1",
                "Renovar um empréstimo",
                ["C3"],
                "o sistema renovasse meu empréstimo uma vez",
                "ficar mais tempo com o livro",
                2,
                _ready("A regra de renovação está definida."),
            ),
            story(
                "US3",
                "F1",
                "Ver meus empréstimos",
                ["C4"],
                "o sistema mostrasse meus empréstimos e as datas",
                "devolver no prazo",
                2,
                _ready("Depende só dos empréstimos registrados."),
            ),
            story(
                "US4",
                "F2",
                "Emprestar pelo quiosque",
                ["C5", "C6"],
                "o quiosque registrasse o empréstimo ao ler meu cartão",
                "emprestar sem esperar atendimento",
                5,
                {
                    "status": "partial",
                    "rationale": "O fluxo pode ser construído sobre um contrato simulado; "
                    "o driver espera a escolha do leitor de cartões.",
                    "independent_of": [
                        {"ref": "Q1", "rationale": "Só a tarefa do driver precisa do modelo escolhido."}
                    ],
                },
            ),
            story(
                "US5",
                "F3",
                "Receber aviso antes do vencimento",
                ["C7"],
                "o sistema me avisasse antes do vencimento",
                "não atrasar a devolução",
                2,
                _ready(
                    "O agendamento do aviso independe do momento exato, que fica parametrizado "
                    "até a resposta à pergunta sobre 'rápido'."
                ),
            ),
            task(
                "T1",
                "US1",
                "Validar o limite de empréstimos ativos",
                ["C1"],
                "Recusar um quarto empréstimo ativo.",
                "Teste com leitor que já tem 3 empréstimos.",
                _ready("Regra confirmada."),
            ),
            task(
                "T2",
                "US1",
                "Registrar o empréstimo com devolução em 14 dias",
                ["C2"],
                "Calcular a data de devolução.",
                "Teste da data calculada.",
                _ready("Prazo confirmado."),
            ),
            task(
                "T3",
                "US2",
                "Renovar uma vez quando não houver reserva",
                ["C3"],
                "Permitir uma renovação e recusar livro reservado.",
                "Testes de segunda renovação e de livro reservado.",
                _ready("Regra confirmada."),
            ),
            task(
                "T4",
                "US3",
                "Listar empréstimos com as datas de devolução",
                ["C4"],
                "Consultar empréstimos ativos do leitor.",
                "Teste com dois empréstimos ativos.",
                _ready("Depende só dos dados de empréstimo."),
            ),
            task(
                "T5",
                "US4",
                "Integrar o driver do leitor de cartões",
                ["C6"],
                "Ler o cartão pelo driver do modelo escolhido.",
                "Teste com o leitor físico escolhido.",
                {
                    "status": "blocked",
                    "rationale": "Sem o modelo não há driver nem protocolo para integrar.",
                    "blocked_by": [
                        {"ref": "Q1", "rationale": "O driver e o protocolo dependem do modelo escolhido."}
                    ],
                },
            ),
            task(
                "T6",
                "US4",
                "Fluxo do quiosque com leitura de cartão simulada",
                ["C5"],
                "Construir o fluxo sobre um contrato simulado do leitor.",
                "Teste do fluxo com o simulador de cartão.",
                {
                    "status": "ready",
                    "rationale": "O contrato simulado separa o fluxo do hardware.",
                    "independent_of": [
                        {"ref": "Q1", "rationale": "O fluxo usa o contrato simulado, não o driver real."}
                    ],
                },
            ),
            {
                "key": "SP1",
                "type": "spike",
                "parent": "US4",
                "title": "Comparar os modelos candidatos de leitor de cartões",
                "claims": ["C6"],
                "content": {
                    "kind": "spike",
                    "question": "Quais modelos atendem ao quiosque e com que protocolo?",
                    "decision": "Recomendação para a escolha do modelo.",
                },
                "readiness": {
                    "status": "ready",
                    "rationale": "Investigação limitada que informa a decisão.",
                    "independent_of": [
                        {"ref": "Q1", "rationale": "O resultado alimenta a resposta, não depende dela."}
                    ],
                },
            },
            task(
                "T7",
                "US5",
                "Agendar o aviso de vencimento",
                ["C7"],
                "Agendar o aviso com antecedência parametrizada.",
                "Teste do agendamento com antecedência configurada.",
                _ready("A antecedência é um parâmetro até a resposta."),
            ),
        ],
        "criteria": [
            {
                "key": "AC1",
                "parent": "US1",
                "condition": "um leitor com 3 empréstimos ativos",
                "trigger": "ele tenta emprestar outro livro",
                "expected_outcomes": ["o empréstimo é recusado"],
                "claims": ["C1"],
            },
            {
                "key": "AC2",
                "parent": "US1",
                "condition": "um empréstimo registrado hoje",
                "trigger": "o sistema calcula a devolução",
                "expected_outcomes": ["a devolução fica em 14 dias"],
                "claims": ["C2"],
            },
            {
                "key": "AC3",
                "parent": "US2",
                "condition": "um empréstimo sem reserva e sem renovação",
                "trigger": "o leitor pede a renovação",
                "expected_outcomes": ["o empréstimo é renovado"],
                "claims": ["C3"],
            },
            {
                "key": "AC4",
                "parent": "US2",
                "condition": "um empréstimo já renovado",
                "trigger": "o leitor pede outra renovação",
                "expected_outcomes": ["a renovação é recusada"],
                "claims": ["C3"],
            },
            {
                "key": "AC5",
                "parent": "US3",
                "text": "A lista mostra cada livro emprestado com sua data de devolução.",
                "expected_outcomes": ["livros e datas listados"],
                "claims": ["C4"],
            },
            {
                "key": "AC6",
                "parent": "US4",
                "condition": "um cartão de leitor válido no quiosque",
                "trigger": "o cartão é lido",
                "expected_outcomes": ["o empréstimo é registrado para o leitor"],
                "claims": ["C5"],
            },
            {
                "key": "AC7",
                "parent": "US5",
                "text": "O aviso chega antes do vencimento com a antecedência definida.",
                "expected_outcomes": ["aviso enviado antes do vencimento"],
                "claims": ["C7"],
                "status": "proposed",
                "rationale": "A fonte não define quanto tempo antes é 'rápido'.",
            },
        ],
        "relations": [
            {
                "source": "US1",
                "target": "US2",
                "type": "predecessor",
                "status": "confirmed",
                "reason": "Só se renova um empréstimo existente.",
            },
            {
                "source": "T6",
                "target": "T5",
                "type": "predecessor",
                "status": "proposed",
                "reason": "O driver substitui o simulador no fluxo pronto.",
            },
        ],
        "questions": [
            {
                "key": "Q1",
                "text": "Qual modelo de leitor de cartões o quiosque usará?",
                "impact": "Sem o modelo, o driver não pode ser integrado.",
                "alternatives": ["Escolher entre os modelos avaliados no spike"],
                "blocking": True,
                "affects": ["US4", "T5", "T6", "SP1"],
            },
            {
                "key": "Q2",
                "text": "Quanto tempo antes do vencimento o aviso deve chegar?",
                "impact": "Define a antecedência do aviso.",
                "blocking": False,
                "affects": ["US5", "AC7"],
            },
        ],
        "dispositions": [
            {
                "claim": "C1",
                "status": "COVERED",
                "covered_by": ["US1", "AC1", "T1"],
                "rationale": "Limite verificado.",
            },
            {
                "claim": "C2",
                "status": "COVERED",
                "covered_by": ["US1", "AC2", "T2"],
                "rationale": "Prazo verificado.",
            },
            {
                "claim": "C3",
                "status": "COVERED",
                "covered_by": ["US2", "AC3", "AC4", "T3"],
                "rationale": "Renovação verificada.",
            },
            {
                "claim": "C4",
                "status": "COVERED",
                "covered_by": ["US3", "AC5", "T4"],
                "rationale": "Lista verificada.",
            },
            {
                "claim": "C5",
                "status": "COVERED",
                "covered_by": ["US4", "AC6", "T6"],
                "rationale": "Fluxo do quiosque.",
            },
            {
                "claim": "C6",
                "status": "QUESTION_REQUIRED",
                "rationale": "Modelo indefinido: pergunta bloqueante e spike.",
            },
            {
                "claim": "C7",
                "status": "PARTIALLY_COVERED",
                "covered_by": ["US5", "AC7", "T7"],
                "rationale": "Antecedência em aberto.",
            },
            {"claim": "C8", "status": "OUT_OF_SCOPE", "rationale": "Exclusão explícita da fonte."},
        ],
    }


INVEST_OK = {
    d: {"rating": "supported", "note": "ok"}
    for d in ("independent", "negotiable", "valuable", "estimable", "small", "testable")
}


def review_payload(run: Run) -> dict[str, Any]:
    p = src_id(run, "prd.md")
    item = lambda k, **kw: {"key": k, "verdict": "pass", "source_support": "supported", **kw}  # noqa: E731
    disp = {
        "R1": ("COVERED", ["AC1"]),
        "R2": ("COVERED", ["AC2"]),
        "R3": ("COVERED", ["AC3", "AC4"]),
        "R4": ("COVERED", ["AC5"]),
        "K1": ("COVERED", ["AC6"]),
        "K2": ("QUESTION_REQUIRED", []),
        "A1": ("PARTIALLY_COVERED", ["AC7"]),
        "X1": ("OUT_OF_SCOPE", []),
    }
    matched = {"R1": "C1", "R2": "C2", "R3": "C3", "R4": "C4", "K1": "C5", "K2": "C6", "A1": "C7", "X1": "C8"}
    obligations = []
    for k, text, _, line, quote in OBLIGATIONS:
        status, covered = disp[k]
        ob = {
            "key": f"O-{k}",
            "text": text,
            "quote": quote,
            "locator": {"source_id": p, "member": "prd.md", "line_start": line},
            "disposition": status,
            "matched_claims": [matched[k]],
            "rationale": "conferido na fonte",
        }
        if covered:
            ob["covered_by"] = covered
        obligations.append(ob)
    stories = {"US1", "US2", "US3", "US4", "US5"}
    buildable = stories | {"T1", "T2", "T3", "T4", "T5", "T6", "T7", "SP1"}
    items = []
    for it in design_payload()["items"]:
        k = it["key"]
        extra: dict[str, Any] = {}
        if k in stories:
            extra.update(invest={**INVEST_OK}, task_sufficiency="sufficient")
        if k in buildable:
            extra["readiness_check"] = "agree"
        items.append(item(k, **extra))
    return {
        "reviewer": {"agent": "reviewer", "model": "test-model", "independence": "separate_agent"},
        "sources_reread": [{"source_id": p, "complete": True}],
        "independent_obligations": obligations,
        "items": items,
        "criteria": [
            item(c["key"])
            if c["key"] != "AC7"
            else item(
                "AC7",
                verdict="concern",
                source_support="proposal_justified",
                notes="Antecedência indefinida; depende da resposta a Q2.",
            )
            for c in design_payload()["criteria"]
        ],
        "duplicates": [],
        "dependencies_reviewed": True,
        "findings": [
            {
                "gate": "G06",
                "classification": "ambiguous_source",
                "severity": "medium",
                "expected": "Antecedência do aviso definida pela fonte.",
                "actual": "A fonte diz apenas 'rápido'.",
                "why": "AC7 não pode ser verificado sem um valor.",
                "impact": "O aviso pode chegar tarde demais.",
                "recommendation": "Responder Q2 e atualizar AC7.",
                "affects": ["US5", "AC7"],
            },
        ],
    }


def designed_run(tmp: Path, **request: Any) -> Run:
    ws = make_workspace(tmp)
    req = normalize_request(synthetic=True, **request)
    run = start(tmp / "out", ws, [("prd.md", "functional")], req)
    read_all(run)
    submit_claims(run, claims_payload(run))
    submit_design(run, design_payload())
    return run
