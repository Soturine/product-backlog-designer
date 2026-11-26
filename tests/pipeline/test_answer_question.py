"""Closing a blocking question through evolution (corrective R4, defects D4/D5).

An approved decision answers the question, and the readiness of the work it blocked must be
recomputed in the same proposal: blockers that cite an answered question are stale and rejected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.finalize import finalize
from pbd.pipeline.refine import RefineError, plan
from pbd.pipeline.review import submit_review
from tests.pipeline.library_fixture import designed_run, review_payload


@pytest.fixture(scope="module")
def backlog(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    import json

    run = designed_run(tmp_path_factory.mktemp("lib"), formats=["md"], title="Biblioteca")
    submit_review(run, review_payload(run))
    finalize(run)
    doc: dict[str, Any] = json.loads(Path(run.path("output/backlog.json")).read_text(encoding="utf-8"))
    return doc


def _ids(backlog: dict[str, Any]) -> tuple[str, str, str]:
    q = next(q for q in backlog["questions"] if q["blocking"])
    blocked = next(i for i in backlog["items"] if (i.get("readiness") or {}).get("status") == "blocked")
    partial = next(i for i in backlog["items"] if (i.get("readiness") or {}).get("status") == "partial")
    return q["id"], blocked["id"], partial["id"]


def _decision() -> dict[str, Any]:
    return {
        "key": "D1",
        "op": "add_decision",
        "text": "O quiosque usará o leitor de cartões modelo A.",
        "status": "approved",
        "evidence": [{"type": "user_statement", "summary": "decisão registrada pelo dono do produto"}],
        "rationale": "resposta da pergunta sobre o leitor",
    }


def test_answering_a_question_requires_recomputed_readiness(backlog: dict[str, Any]) -> None:
    qid, blocked, partial = _ids(backlog)
    answer = {
        "key": "A1",
        "op": "answer_question",
        "target": qid,
        "decision": "change:D1",
        "rationale": "decidido",
    }
    with pytest.raises(RefineError) as exc:
        plan(backlog, {"author": {"agent": "a"}, "changes": [_decision(), answer]})
    assert any("which is answered: recompute readiness" in e for e in exc.value.errors)
    ready = {"status": "ready", "rationale": "o modelo foi escolhido"}
    doc = plan(
        backlog,
        {
            "author": {"agent": "a"},
            "changes": [
                _decision(),
                answer,
                {"key": "R1", "op": "set_readiness", "target": blocked, "readiness": ready, "rationale": "x"},
                {"key": "R2", "op": "set_readiness", "target": partial, "readiness": ready, "rationale": "x"},
            ],
        },
    )
    after = {c["key"]: c["after"] for c in doc["changes"]}
    assert after["A1"]["status"] == "answered" and after["A1"]["answer_decision"].startswith("PBD-DEC-")
    assert after["R1"] == ready


def test_only_an_approved_decision_answers_and_unknown_fields_are_refused(backlog: dict[str, Any]) -> None:
    qid, blocked, _ = _ids(backlog)
    proposed = {**_decision(), "status": "proposed"}
    answer = {"key": "A1", "op": "answer_question", "target": qid, "decision": "change:D1", "rationale": "x"}
    with pytest.raises(RefineError) as exc:
        plan(backlog, {"author": {"agent": "a"}, "changes": [proposed, answer]})
    assert any("only an approved decision answers" in e for e in exc.value.errors)
    stray = {"key": "F1", "op": "set_field", "target": blocked, "field": "readiness", "state": "proposed",
             "value": "ready", "rationale": "x"}  # fmt: skip
    with pytest.raises(RefineError) as exc:
        plan(backlog, {"author": {"agent": "a"}, "changes": [stray]})
    assert any("unknown field 'readiness'" in e for e in exc.value.errors)
