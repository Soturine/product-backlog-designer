"""M5 evolution: source diffs, decisions superseding claims, lineage, human edits, staleness."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline import refine
from pbd.pipeline.evolution import diff_sources, stale_artifacts, summarize
from pbd.pipeline.finalize import finalize
from pbd.pipeline.planning import plan as make_plan
from pbd.pipeline.review import submit_review
from tests.pipeline.helpers import designed_run
from tests.pipeline.test_review_finalize import review_payload


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    run = designed_run(tmp_path_factory.mktemp("evo"), title="Horta")
    submit_review(run, review_payload(run))
    finalize(run)
    doc: dict[str, Any] = json.loads(run.path("output/backlog.json").read_text(encoding="utf-8"))
    doc["_keys"] = json.loads(run.path("stages/backlog.draft.json").read_text(encoding="utf-8"))["keys"]
    return doc


def _by_key(base: dict[str, Any], key: str) -> str:
    return next(pid for pid, k in base["_keys"].items() if k == key)


def _clean(base: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in base.items() if k != "_keys"}


def test_source_diff_separates_formatting_from_content(tmp_path: Path) -> None:
    old, new = tmp_path / "v1", tmp_path / "v2"
    for root in (old, new):
        (root / "docs").mkdir(parents=True)
    (old / "prd.md").write_text("# PRD\n\nUm membro pode reservar.\n", encoding="utf-8")
    (new / "prd.md").write_text("#  PRD\n\num   MEMBRO pode reservar\n", encoding="utf-8")
    (old / "docs" / "adr.md").write_text("Status: proposto\nDecisão: A\n", encoding="utf-8")
    (new / "docs" / "adr.md").write_text("Status: aprovado\nDecisão: B\n", encoding="utf-8")
    (old / "docs" / "same.md").write_text("igual\n", encoding="utf-8")
    (new / "docs" / "same.md").write_text("igual\n", encoding="utf-8")
    (new / "docs" / "novo.md").write_text("novo\n", encoding="utf-8")
    doc = diff_sources(old, new, ["prd.md", "docs"])
    changes = {m["path"]: m["change"] for s in doc["sources"] for m in s["members"]}
    assert changes == {
        "prd.md": "formatting_only",
        "adr.md": "content",
        "same.md": "identical",
        "novo.md": "added",
    }
    hunk = next(m for s in doc["sources"] for m in s["members"] if m["path"] == "adr.md")["hunks"][0]
    assert hunk["old"] == ["Status: proposto", "Decisão: A"] and hunk["new_lines"] == [1, 2]
    assert doc["sources"][0]["change"] == "formatting_only" and doc["sources"][1]["change"] == "content"
    with pytest.raises(FileNotFoundError):
        diff_sources(old, new, ["missing.md"])


def _supersede_c3(base: dict[str, Any]) -> dict[str, Any]:
    c3 = _by_key(base, "C3")
    return {
        "author": {"agent": "evolver", "model": "test-model"},
        "changes": [
            {
                "key": "K1",
                "op": "add_decision",
                "status": "approved",
                "text": "Lista Minhas reservas removida da v2.",
                "supersedes_claims": [c3],
                "evidence": [{"type": "user_statement", "summary": "ADR-002 aprovado"}],
                "rationale": "ADR-002",
            },
            {
                "key": "K2",
                "op": "set_criterion_status",
                "target": _by_key(base, "AC4"),
                "status": "superseded",
                "rationale": "ADR-002",
            },
            {
                "key": "K3",
                "op": "supersede_item",
                "target": _by_key(base, "US2"),
                "superseded_by": ["change:K1"],
                "rationale": "ADR-002",
            },
            {
                "key": "K4",
                "op": "retrace",
                "target": _by_key(base, "E1"),
                "claim_refs": [_by_key(base, "C1"), _by_key(base, "C2")],
                "rationale": "C3 superseded",
            },
            {
                "key": "K5",
                "op": "retrace",
                "target": _by_key(base, "F1"),
                "claim_refs": [_by_key(base, "C1"), _by_key(base, "C2"), _by_key(base, "C5")],
                "rationale": "C3 superseded",
            },
        ],
    }


def test_decision_supersedes_claims_and_work_without_deleting(base: dict[str, Any]) -> None:
    b = _clean(base)
    plan = refine.plan(b, _supersede_c3(base))
    out = refine.apply(b, plan, ["all"], plan["plan_digest"])["backlog"]
    assert len(out["items"]) == len(b["items"]) and len(out["criteria"]) == len(b["criteria"])
    claim = next(c for c in out["claims"] if c["id"] == _by_key(base, "C3"))
    decision = out["decisions"][-1]
    assert claim["disposition"]["status"] == "SUPERSEDED" and claim["temporal"]["superseded_by"] == [
        decision["id"]
    ]
    story = next(i for i in out["items"] if i["id"] == _by_key(base, "US2"))
    assert story["temporal"] == {
        "status": "superseded",
        "superseded_by": [decision["id"]],
        "superseded_reason": "ADR-002",
    }
    summary = summarize(b, plan)
    assert (
        summary["deletions"] == 0 and summary["counts"]["update"] == 3
    )  # US2 (criterion + supersession), E1, F1 and summary["decisions"][0]["status"] == "approved"


def test_superseding_a_claim_still_traced_by_active_work_is_refused(base: dict[str, Any]) -> None:
    prop = _supersede_c3(base)
    prop["changes"] = prop["changes"][:1]  # decision only: AC4/US2/E1/F1 would still rely on C3
    with pytest.raises(refine.RefineError) as err:
        refine.plan(_clean(base), prop)
    assert any("stale_scope" in e or "inactive claim" in e for e in err.value.errors)


def test_split_and_merge_record_lineage(base: dict[str, Any]) -> None:
    b = _clean(base)
    us1, us2 = _by_key(base, "US1"), _by_key(base, "US2")
    prop = {
        "author": {"agent": "evolver"},
        "changes": [
            {
                "key": "S1",
                "op": "split_item",
                "target": us1,
                "rationale": "two flows",
                "into": [
                    {"title": "Reservar canteiro livre", "claim_refs": [_by_key(base, "C1")]},
                    {"title": "Rejeitar canteiro ocupado", "claim_refs": [_by_key(base, "C2")]},
                ],
            },
        ],
    }
    out = refine.apply(b, (p := refine.plan(b, prop)), ["all"], p["plan_digest"])["backlog"]
    parts = [i for i in out["items"] if (i.get("lineage") or {}).get("split_from") == [us1]]
    assert (
        len(parts) == 2
        and next(i for i in out["items"] if i["id"] == us1)["temporal"]["status"] == "superseded"
    )
    merge = {
        "author": {"agent": "evolver"},
        "changes": [
            {
                "key": "M1",
                "op": "merge_items",
                "targets": [us1, us2],
                "title": "Reservas do membro",
                "rationale": "one flow",
            }
        ],
    }
    merged = refine.apply(b, (m := refine.plan(b, merge)), ["all"], m["plan_digest"])["backlog"]
    new = next(i for i in merged["items"] if (i.get("lineage") or {}).get("merged_from"))
    assert sorted(new["lineage"]["merged_from"]) == sorted([us1, us2])
    assert set(new["claim_refs"]) >= {_by_key(base, "C1"), _by_key(base, "C3")}


def test_title_change_keeps_identity_and_recreation_is_refused(base: dict[str, Any]) -> None:
    b = _clean(base)
    us1 = next(i for i in b["items"] if i["id"] == _by_key(base, "US1"))
    rename = {
        "author": {"agent": "e"},
        "changes": [
            {
                "key": "R",
                "op": "update_title",
                "target": us1["id"],
                "value": "Reservar um canteiro",
                "rationale": "wording",
            }
        ],
    }
    out = refine.apply(b, (p := refine.plan(b, rename)), ["all"], p["plan_digest"])["backlog"]
    assert any(i["id"] == us1["id"] and i["title"] == "Reservar um canteiro" for i in out["items"])
    recreate = {
        "author": {"agent": "e"},
        "changes": [
            {
                "key": "A",
                "op": "add_item",
                "type": "story",
                "parent": us1["parent"],
                "title": us1["title"].upper(),
                "rationale": "regenerated",
            }
        ],
    }
    with pytest.raises(refine.RefineError, match="would recreate"):
        refine.plan(b, recreate)


def test_human_edits_are_conflicts_needing_explicit_approval(base: dict[str, Any]) -> None:
    b = copy.deepcopy(_clean(base))
    us1 = next(i for i in b["items"] if i["id"] == _by_key(base, "US1"))
    us1["origin"] = "human_edited"
    change = {
        "key": "H",
        "op": "update_title",
        "target": us1["id"],
        "value": "Outro",
        "rationale": "source changed",
    }
    with pytest.raises(refine.RefineError, match="edited or accepted by a person"):
        refine.plan(b, {"author": {"agent": "e"}, "changes": [change]})
    plan = refine.plan(b, {"author": {"agent": "e"}, "changes": [{**change, "override_human_edit": True}]})
    assert plan["changes"][0]["requires_explicit_approval"] is True
    assert summarize(b, plan)["counts"]["conflict"] == 1
    with pytest.raises(refine.RefineError, match="approve at least one"):
        refine.apply(b, plan, ["all"], plan["plan_digest"])  # 'all' never includes overwrites of human edits
    applied = refine.apply(b, plan, ["H"], plan["plan_digest"])
    assert applied["result"]["applied"] == ["H"]


def test_noop_is_unchanged_and_replay_is_refused(base: dict[str, Any]) -> None:
    b = _clean(base)
    us1 = next(i for i in b["items"] if i["id"] == _by_key(base, "US1"))
    noop = {
        "author": {"agent": "e"},
        "changes": [
            {
                "key": "N",
                "op": "update_title",
                "target": us1["id"],
                "value": us1["title"],
                "rationale": "no change",
            }
        ],
    }
    plan = refine.plan(b, noop)
    assert plan["changes"][0]["noop"] is True and summarize(b, plan)["counts"].get("update", 0) == 0
    rename = {
        "author": {"agent": "e"},
        "changes": [
            {"key": "R", "op": "update_title", "target": us1["id"], "value": "Novo título", "rationale": "x"}
        ],
    }
    p = refine.plan(b, rename)
    once = refine.apply(b, p, ["all"], p["plan_digest"])["backlog"]
    with pytest.raises(refine.RefineError, match="conflict"):
        refine.apply(once, p, ["all"], p["plan_digest"])  # replay on the new version is refused


def test_staleness_invalidates_plans_and_approvals(base: dict[str, Any], tmp_path: Path) -> None:
    b = _clean(base)
    (tmp_path / "sprint-plan.json").write_text(json.dumps(make_plan(b)), encoding="utf-8")
    rp = refine.plan(b, _supersede_c3(base))
    (tmp_path / "refinement-plan.json").write_text(json.dumps(rp), encoding="utf-8")
    (tmp_path / "notes.json").write_text("[1, 2]", encoding="utf-8")
    assert stale_artifacts(tmp_path, b)["stale"] == []
    newer = refine.apply(b, rp, ["all"], rp["plan_digest"])["backlog"]
    report = stale_artifacts(tmp_path, newer)
    assert sorted(s["path"] for s in report["stale"]) == ["refinement-plan.json", "sprint-plan.json"]


def test_evolve_cli_round_trip(
    base: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from pbd.cli import main

    b = _clean(base)
    (tmp_path / "b.json").write_text(json.dumps(b), encoding="utf-8")
    (tmp_path / "p.json").write_text(json.dumps(_supersede_c3(base)), encoding="utf-8")
    old, new = tmp_path / "v1", tmp_path / "v2"
    old.mkdir()
    new.mkdir()
    (old / "adr.md").write_text("Status: proposto\n", encoding="utf-8")
    (new / "adr.md").write_text("Status: aprovado\n", encoding="utf-8")
    out = tmp_path / "o"
    assert (
        main(
            ["evolve", "diff", "--old", str(old), "--new", str(new), "--source", "adr.md", "--out", str(out)]
        )
        == 0
    )
    assert (
        main(
            [
                "evolve",
                "plan",
                "--backlog",
                str(tmp_path / "b.json"),
                "--file",
                str(tmp_path / "p.json"),
                "--diff",
                str(out / "source-diff.json"),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    digest_ = json.loads(
        capsys.readouterr().out.split("\n{", 1)[-1].join(["{", ""])
        if False
        else (out / "evolution-plan.json").read_text(encoding="utf-8")
    )["plan_digest"]
    page = (out / "evolution-report.html").read_text(encoding="utf-8")
    assert "Plano de evolução" in page and "Conteúdo alterado" in page and "Exclusões: nenhuma." in page
    assert (
        main(
            [
                "evolve",
                "apply",
                "--backlog",
                str(tmp_path / "b.json"),
                "--plan",
                str(out / "evolution-plan.json"),
                "--approve",
                "all",
                "--plan-digest",
                digest_,
                "--out",
                str(out),
            ]
        )
        == 0
    )
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "sprint-plan.json").write_text(json.dumps(make_plan(b)), encoding="utf-8")
    assert (
        main(
            [
                "evolve",
                "stale",
                "--backlog",
                str(out / "backlog.evolved.json"),
                "--dir",
                str(tmp_path / "artifacts"),
            ]
        )
        == 1
    )
