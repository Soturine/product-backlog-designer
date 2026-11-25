"""M6: one synthetic project through every mode, sharing the same evidence and rendering layers.

generate → audit → compare → refine → plan → evolve (ADR) → stale plan detected → re-plan →
local Azure package → mock prepare/approve/apply/verify → FTD handoff. No tracker is contacted
(the whole flow runs inside the zero-network guard).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pbd.integrations.authority import RemoteAuthority
from pbd.integrations.azure import publish
from pbd.integrations.azure.snapshot import load_snapshot
from pbd.integrations.azure.transport import FakeAzure
from pbd.pipeline import refine
from pbd.pipeline.compare import finalize_comparison, submit_comparison
from pbd.pipeline.design import submit_claims
from pbd.pipeline.evolution import stale_artifacts
from pbd.pipeline.finalize import finalize
from pbd.pipeline.handoff import build_handoff
from pbd.pipeline.planning import is_stale, plan
from pbd.pipeline.review import submit_review
from pbd.pipeline.run import normalize_request, start
from pbd.profiles import load_profile
from pbd.render.exports import azure_package
from pbd.security.network import offline
from tests.pipeline import test_audit, test_compare
from tests.pipeline.helpers import claims_payload, designed_run, make_workspace, read_all
from tests.pipeline.test_evolution import _supersede_c3
from tests.pipeline.test_review_finalize import review_payload

NS = "fabrikam-mock/backlog-mock"


def _set_points(backlog: dict[str, Any], claims: dict[str, str]) -> dict[str, Any]:
    """Refinement proposal that records source-stated estimates as confirmed fields."""
    stories = [i for i in backlog["items"] if i["type"] == "story"]
    return {
        "author": {"agent": "refiner", "model": "test-model"},
        "changes": [
            {
                "key": f"P{n}",
                "op": "set_field",
                "target": s["id"],
                "field": "story_points",
                "state": "confirmed",
                "value": 3 + n,
                "claim_refs": [s["claim_refs"][0]],
                "rationale": "estimate stated by the team source",
            }
            for n, s in enumerate(stories)
        ],
    }


def test_every_mode_on_one_project(tmp_path: Path) -> None:
    with offline() as ledger:
        # 1. generate
        gen = designed_run(tmp_path / "gen", formats=["azure"], profile="azure-agile", title="Horta")
        submit_review(gen, review_payload(gen))
        finalize(gen)
        backlog = json.loads(gen.path("output/backlog.json").read_text(encoding="utf-8"))
        keys = json.loads(gen.path("stages/backlog.draft.json").read_text(encoding="utf-8"))["keys"]
        assert gen.path("output/report.html").exists()

        # 2. audit the generated backlog against the same sources (the generated file is a baseline)
        ws = make_workspace(tmp_path / "aud")
        (ws / "generated.json").write_text(json.dumps(backlog), encoding="utf-8")
        aud = start(
            tmp_path / "aud" / "out",
            ws,
            test_audit.SOURCES,
            normalize_request(mode="audit", synthetic=True),
            baselines=["generated.json"],
        )
        read_all(aud)
        compiled = submit_claims(aud, claims_payload(aud))
        assert compiled["baseline_compiled"]["items"] == len(backlog["items"])

        # 3. compare two baselines
        ws2 = make_workspace(tmp_path / "cmp")
        (ws2 / "left.json").write_text(json.dumps(test_compare.LEFT), encoding="utf-8")
        (ws2 / "right.json").write_text(json.dumps(test_compare.RIGHT), encoding="utf-8")
        cmp_ = start(
            tmp_path / "cmp" / "out",
            ws2,
            test_compare.SOURCES,
            normalize_request(mode="compare", synthetic=True),
            baselines=["left.json", "right.json"],
        )
        read_all(cmp_)
        submit_claims(cmp_, claims_payload(cmp_))
        submit_comparison(cmp_, test_compare.payload(cmp_))
        assert finalize_comparison(cmp_)["mappings"] == 2

        # 4. refine: confirmed estimates from a source
        rp = refine.plan(backlog, _set_points(backlog, keys))
        refined = refine.apply(backlog, rp, ["all"], rp["plan_digest"])["backlog"]

        # 5. plan with capacity
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        sprint_plan = plan(refined, {"capacity": {"unit": "story_points", "per_sprint": 8}})
        (artifacts / "sprint-plan.json").write_text(json.dumps(sprint_plan), encoding="utf-8")
        assert sprint_plan["sprints"] and all(s["load"] <= s["capacity"] for s in sprint_plan["sprints"])

        # 6. evolve: an approved ADR supersedes a requirement
        evo = _supersede_c3({**refined, "_keys": keys})
        ep = refine.plan(refined, evo)
        evolved = refine.apply(refined, ep, ["all"], ep["plan_digest"])["backlog"]
        assert is_stale(sprint_plan, evolved)
        assert [s["path"] for s in stale_artifacts(artifacts, evolved)["stale"]] == ["sprint-plan.json"]
        replanned = plan(evolved, {"capacity": {"unit": "story_points", "per_sprint": 8}})
        superseded = next(
            i["id"] for i in evolved["items"] if (i.get("temporal") or {}).get("status") == "superseded"
        )
        assert superseded in {x["item"] for x in replanned["sequence"]}  # still visible, flagged by lineage

        # 7. local package and mock publication
        package, _ = azure_package(evolved, load_profile("azure-agile"))
        fake = FakeAzure(namespace=NS)
        (tmp_path / "snap.json").write_text(json.dumps(fake.snapshot_doc()), encoding="utf-8")
        prepared = publish.prepare(evolved, package, load_snapshot(tmp_path / "snap.json"), NS)
        approved = publish.approve(prepared, NS, "owner", "2026-11-25T12:00:00Z")
        receipt = publish.apply(
            approved, fake, RemoteAuthority(opted_in=True, transport="mock"), tmp_path / "j.jsonl"
        )
        verified = publish.verify(approved, receipt, fake)
        assert verified["verification"]["status"] == "MOCK_VERIFIED" and verified["transport"] == "mock"

        # 8. FTD handoff: originals + roles, criteria as seeds, superseded work not seeded
        handoff = build_handoff(evolved, keys)
        assert {s["ftd_role"] for s in handoff["sources"]} == {"FUNCTIONAL_AUTHORITY"}
        assert handoff["test_cases"] == [] and "not an authority" in handoff["authority_note"]
        seeded = " ".join(s["text"] for s in handoff["ftd_request_draft"]["seeds"])
        assert "Minhas reservas" not in seeded  # superseded by the ADR
        assert handoff["backlog_digest"] != build_handoff(backlog, keys)["backlog_digest"]
    assert ledger.blocked == [] and ledger.allowed_local == []  # nothing even tried to connect
