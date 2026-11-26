"""M3: local snapshots, discovered profiles and the mock-only prepare/approve/apply/verify flow."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from pbd.integrations.authority import AuthorizationDenied, RemoteAuthority
from pbd.integrations.azure import publish
from pbd.integrations.azure.snapshot import SnapshotError, batches, discover_profile, load_snapshot
from pbd.integrations.azure.transport import FakeAzure, Fault
from pbd.pipeline.finalize import finalize
from pbd.pipeline.review import submit_review
from pbd.validation.schema import validate
from tests.pipeline.helpers import designed_run
from tests.pipeline.test_review_finalize import review_payload

NS = "fabrikam-mock/backlog-mock"
MOCK = RemoteAuthority(opted_in=True, transport="mock")
NOW = "2026-11-25T12:00:00Z"


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], dict[str, Any]]:
    run = designed_run(tmp_path_factory.mktemp("az"), formats=["azure"], profile="azure-agile", title="Horta")
    submit_review(run, review_payload(run))
    finalize(run)
    backlog = json.loads(run.path("output/backlog.json").read_text(encoding="utf-8"))
    package = json.loads(run.path("output/azure/azure-import.json").read_text(encoding="utf-8"))
    return backlog, package


def _snap(fake: FakeAzure, tmp: Path, name: str = "snap.json") -> dict[str, Any]:
    path = tmp / name
    path.write_text(json.dumps(fake.snapshot_doc()), encoding="utf-8")
    return load_snapshot(path)


def _approved(
    backlog: dict[str, Any], package: dict[str, Any], fake: FakeAzure, tmp: Path, **kw: Any
) -> dict[str, Any]:
    plan = publish.prepare(backlog, package, _snap(fake, tmp), NS, **kw)
    assert validate("publication-plan", plan) == []
    return publish.approve(plan, NS, "owner", NOW)


def test_snapshot_import_keeps_unknown_and_truncation_visible(tmp_path: Path) -> None:
    page = {
        "value": [{"id": 7, "rev": 3}, {"id": 8, "rev": 1, "fields": {"System.WorkItemType": "Task"}}],
        "continuationToken": "abc",
    }
    p = tmp_path / "page.json"
    p.write_text(json.dumps(page), encoding="utf-8")
    with pytest.raises(SnapshotError, match="target"):
        load_snapshot(p)
    snap = load_snapshot(p, {"organization": "o", "project": "p"})
    assert (
        snap["items"][0]["fields_state"] == "unavailable"
        and snap["items"][0]["relations_state"] == "unavailable"
    )
    assert any("truncated" in n for n in snap["notes"]) and snap["metadata_state"] == "unavailable"
    dup = {
        "kind": "pbd.azure-snapshot",
        "target": {"organization": "o", "project": "p"},
        "pages": [
            {"value": [{"id": 1, "rev": 1, "fields": {}}]},
            {"value": [{"id": 1, "rev": 2, "fields": {}}]},
        ],
    }
    p.write_text(json.dumps(dup), encoding="utf-8")
    with pytest.raises(SnapshotError, match="different revisions"):
        load_snapshot(p)


def test_discovered_profile_and_batches(tmp_path: Path) -> None:
    doc = {
        "kind": "pbd.azure-snapshot",
        "target": {"organization": "o", "project": "p"},
        "pages": [{"value": []}],
        "metadata": {
            "work_item_types": [
                {
                    "name": "Product Backlog Item",
                    "fields": [
                        {"referenceName": "System.Title", "alwaysRequired": True},
                        {"referenceName": "Microsoft.VSTS.Common.Priority", "allowedValues": [1, 2, 3, 4]},
                    ],
                },
                {"name": "Feature", "fields": []},
                {"name": "Epic", "fields": []},
                {"name": "Task", "fields": []},
                {"name": "Bug", "fields": []},
            ]
        },
    }
    p = tmp_path / "s.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    prof = discover_profile(load_snapshot(p))
    assert prof["process"] == "scrum" and prof["types"]["story"] == "Product Backlog Item"
    assert prof["fields"]["Microsoft.VSTS.Common.Priority"]["allowed_values"] == [1, 2, 3, 4]
    assert (
        prof["fields"]["System.Title"]["required_in"] == ["Product Backlog Item"]
        and prof["verified"] is False
    )
    assert [len(b) for b in batches(list(range(450)))] == [200, 200, 50]
    with pytest.raises(SnapshotError):
        batches([1], 201)


def test_full_mock_flow_is_verified_and_idempotent(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    fake = FakeAzure(namespace=NS)
    plan = _approved(backlog, package, fake, tmp_path)
    assert {o["action"] for o in plan["operations"]} == {"CREATE"}
    assert publish.preview(plan)["deletes"] == 0
    receipt = publish.apply(plan, fake, MOCK, tmp_path / "journal.jsonl")
    assert validate("publication-receipt", receipt) == []
    assert {r["outcome"] for r in receipt["results"]} == {"APPLIED"}
    verified = publish.verify(plan, receipt, fake)
    assert verified["verification"]["status"] == "MOCK_VERIFIED", verified["verification"]["deviations"]
    children = [w for w in fake.items.values() if w["relations"]]
    assert len(children) == len(package["work_items"]) - 1  # every item but the epic has a parent
    for w in fake.items.values():
        for f in publish.FORBIDDEN_REFS:
            assert f not in w["fields"]
    again = publish.prepare(backlog, package, _snap(fake, tmp_path, "s2.json"), NS)
    assert {o["action"] for o in again["operations"]} == {"UNCHANGED"}
    before = len(fake.items)
    rerun = publish.apply(plan, fake, MOCK, tmp_path / "journal.jsonl")
    assert len(fake.items) == before and all("journal" in r.get("detail", "") for r in rerun["results"])


def test_authorization_is_exact(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    fake = FakeAzure(namespace=NS)
    plan = publish.prepare(backlog, package, _snap(fake, tmp_path), NS)
    with pytest.raises(AuthorizationDenied, match="not approved"):
        publish.apply(plan, fake, MOCK, tmp_path / "j.jsonl")
    approved = publish.approve(plan, NS, "owner", NOW)
    with pytest.raises(AuthorizationDenied, match="disabled"):
        publish.apply(approved, fake, RemoteAuthority(), tmp_path / "j.jsonl")
    tampered = copy.deepcopy(approved)
    tampered["operations"][0]["fields"]["System.Title"] = "outro"
    with pytest.raises(AuthorizationDenied, match="stale"):
        publish.apply(tampered, fake, MOCK, tmp_path / "j.jsonl")
    other = FakeAzure(namespace="other-mock/x")
    with pytest.raises(publish.PublishError):
        publish.approve(plan, "other-mock/x", "owner", NOW)
    live_like = copy.copy(other)
    live_like.kind = "live"
    with pytest.raises(AuthorizationDenied, match="only the mock"):
        publish.apply(
            approved, live_like, RemoteAuthority(opted_in=True, transport="live"), tmp_path / "j.jsonl"
        )
    assert fake.items == {}


def test_throttling_and_server_errors_are_retried_with_bounds(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    fake = FakeAzure(
        namespace=NS,
        faults=[Fault("create", 429, nth=1, retry_after=7.0), Fault("create", 503, nth=3, times=2)],
    )
    waits: list[float] = []
    receipt = publish.apply(
        _approved(backlog, package, fake, tmp_path), fake, MOCK, tmp_path / "j.jsonl", sleep=waits.append
    )
    assert 7.0 in waits and {r["outcome"] for r in receipt["results"]} == {"APPLIED"}
    fake2 = FakeAzure(namespace=NS, faults=[Fault("create", 500, times=99)])
    out = publish.apply(
        _approved(backlog, package, fake2, tmp_path), fake2, MOCK, tmp_path / "j2.jsonl", retries=2
    )
    assert out["results"][0]["outcome"] == "FAILED" and fake2.items == {}


def test_auth_failure_stops_the_run(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    fake = FakeAzure(namespace=NS, faults=[Fault("create", 401, nth=2)])
    receipt = publish.apply(_approved(backlog, package, fake, tmp_path), fake, MOCK, tmp_path / "j.jsonl")
    outcomes = [r["outcome"] for r in receipt["results"]]
    assert outcomes[0] == "APPLIED" and outcomes[1] == "FAILED" and set(outcomes[2:]) == {"SKIPPED"}


def test_lost_response_is_reconciled_without_duplicates(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    fake = FakeAzure(namespace=NS, faults=[Fault("create", "timeout", nth=1, applied=True)])
    receipt = publish.apply(_approved(backlog, package, fake, tmp_path), fake, MOCK, tmp_path / "j.jsonl")
    assert "reconciled" in receipt["results"][0]["detail"]
    assert len(fake.items) == len(package["work_items"])  # no duplicate create


def test_failed_parent_link_is_partial_and_verification_mismatches(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    child = package["work_items"][1]["pbd_id"]
    fake = FakeAzure(namespace=NS, faults=[Fault("update", 400, nth=1, times=1)])
    plan = _approved(backlog, package, fake, tmp_path)
    receipt = publish.apply(plan, fake, MOCK, tmp_path / "j.jsonl", retries=0)
    partial = [r for r in receipt["results"] if r["outcome"] == "PARTIAL"]
    assert partial and "parent link failed" in partial[0]["detail"]
    verified = publish.verify(plan, receipt, fake)
    assert verified["verification"]["status"] == "MISMATCH"
    assert child  # the next items still had their parents resolved


def test_revision_conflict_and_human_edits_are_never_overwritten(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    fake = FakeAzure(namespace=NS)
    plan = _approved(backlog, package, fake, tmp_path)
    receipt = publish.verify(plan, publish.apply(plan, fake, MOCK, tmp_path / "j.jsonl"), fake)
    state = publish.published_state(plan, receipt, package, fake)
    changed = copy.deepcopy(package)
    changed["work_items"][0]["fields"]["System.Title"] = "Título refinado pela PBD"
    target = next(
        w
        for w in fake.items.values()
        if w["fields"]["System.Title"] == package["work_items"][0]["fields"]["System.Title"]
    )
    target["fields"]["System.Title"] = "Título editado por uma pessoa"
    target["rev"] += 1
    changed["backlog_digest"] = package["backlog_digest"]
    plan2 = publish.prepare(backlog, changed, _snap(fake, tmp_path, "s3.json"), NS, published=state)
    op = next(o for o in plan2["operations"] if o["pbd_id"] == package["work_items"][0]["pbd_id"])
    assert op["action"] == "CONFLICT" and "edited in the target" in op["reason"]
    # without the human edit, the same change is an UPDATE bound to the revision; a concurrent write fails it
    fresh = FakeAzure(namespace=NS)
    p1 = _approved(backlog, package, fresh, tmp_path)
    publish.apply(p1, fresh, MOCK, tmp_path / "k.jsonl")
    p2 = publish.approve(
        publish.prepare(backlog, changed, _snap(fresh, tmp_path, "s4.json"), NS), NS, "owner", NOW
    )
    assert any(o["action"] == "UPDATE" for o in p2["operations"])
    wid = int(next(o for o in p2["operations"] if o["action"] == "UPDATE")["external_ref"]["native_id"])
    fresh.items[wid]["rev"] += 1  # someone writes between snapshot and apply
    out = publish.apply(p2, fresh, MOCK, tmp_path / "k2.jsonl")
    failed = [r for r in out["results"] if r["outcome"] == "FAILED"]
    assert (
        failed
        and "412" in failed[0]["detail"]
        and fresh.items[wid]["fields"]["System.Title"] != "Título refinado pela PBD"
    )


def test_ambiguous_identity_and_type_mismatch_are_conflicts(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    pid = package["work_items"][0]["pbd_id"]
    fake = FakeAzure(namespace=NS)
    for wid in (1, 2):
        fake.items[wid] = {
            "id": wid,
            "rev": 1,
            "relations": [],
            "fields": {"System.WorkItemType": "Epic", "System.Tags": f"pbd-id:{pid}"},
        }
    plan = publish.prepare(backlog, package, _snap(fake, tmp_path), NS)
    assert plan["operations"][0]["action"] == "CONFLICT" and "ambiguous" in plan["operations"][0]["reason"]
    assert all(o["action"] == "DEFERRED" for o in plan["operations"][1:2])


def test_incomplete_readback_is_a_mismatch(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    fake = FakeAzure(namespace=NS)
    plan = _approved(backlog, package, fake, tmp_path)
    receipt = publish.apply(plan, fake, MOCK, tmp_path / "j.jsonl")
    fake.faults.append(Fault("get", "incomplete"))
    verified = publish.verify(plan, receipt, fake)
    assert verified["verification"]["status"] == "MISMATCH"
    assert any("incomplete" in d for d in verified["verification"]["deviations"])
    assert verified["verification"]["status"] != "LIVE_VERIFIED"


def test_unicode_html_round_trip(artifacts: Any, tmp_path: Path) -> None:
    backlog, package = artifacts
    fake = FakeAzure(namespace=NS)
    plan = _approved(backlog, package, fake, tmp_path)
    publish.apply(plan, fake, MOCK, tmp_path / "j.jsonl")
    story = next(w for w in fake.items.values() if w["fields"]["System.WorkItemType"] == "User Story")
    assert "<strong>Eu como</strong>" in story["fields"]["System.Description"]
    assert story["multilineFieldsFormat"]["System.Description"] == "html"
    assert story["multilineFieldsFormat"]["Microsoft.VSTS.Common.AcceptanceCriteria"] == "html"
    assert any("ç" in str(v) or "ã" in str(v) for w in fake.items.values() for v in w["fields"].values())


def test_cli_mock_round_trip(artifacts: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from pbd.cli import main

    backlog, package = artifacts
    (tmp_path / "b.json").write_text(json.dumps(backlog), encoding="utf-8")
    (tmp_path / "p.json").write_text(json.dumps(package), encoding="utf-8")
    empty = {
        "kind": "pbd.azure-snapshot",
        "target": {"organization": "fabrikam-mock", "project": "backlog-mock"},
        "pages": [{"value": []}],
    }
    (tmp_path / "s.json").write_text(json.dumps(empty), encoding="utf-8")
    out = str(tmp_path / "o")
    assert main(["azure", "snapshot", "--file", str(tmp_path / "s.json"), "--out", out]) == 0
    assert (
        main(
            [
                "azure",
                "prepare",
                "--backlog",
                str(tmp_path / "b.json"),
                "--package",
                str(tmp_path / "p.json"),
                "--snapshot",
                str(tmp_path / "s.json"),
                "--target",
                NS,
                "--out",
                out,
            ]
        )
        == 0
    )
    plan = f"{out}/publication-plan.json"
    assert (
        main(["azure", "apply", "--plan", plan, "--mock-state", str(tmp_path / "m.json"), "--out", out]) != 0
    )
    assert "not approved" in capsys.readouterr().out
    assert main(["azure", "approve", "--plan", plan, "--target", NS, "--by", "owner", "--out", out]) == 0
    approved = f"{out}/publication-plan.approved.json"
    assert (
        main(["azure", "apply", "--plan", approved, "--mock-state", str(tmp_path / "m.json"), "--out", out])
        == 0
    )
    assert (
        main(
            [
                "azure",
                "verify",
                "--plan",
                approved,
                "--receipt",
                f"{out}/publication-receipt.json",
                "--package",
                str(tmp_path / "p.json"),
                "--mock-state",
                str(tmp_path / "m.json"),
                "--out",
                out,
            ]
        )
        == 0
    )
    capsys.readouterr()
    verified = json.loads((tmp_path / "o" / "publication-receipt.verified.json").read_text(encoding="utf-8"))
    assert verified["verification"]["status"] == "MOCK_VERIFIED" and verified["transport"] == "mock"
    page = (tmp_path / "o" / "publication-report.html").read_text(encoding="utf-8")
    assert "Applied (mock)" in page and "Verified on the mock" in page and "PBD never deletes" in page
    with pytest.raises(SystemExit):
        main(["azure", "apply", "--plan", approved, "--transport", "live", "--mock-state", "x", "--out", out])


def test_mock_publication_opens_no_socket(artifacts: Any, tmp_path: Path) -> None:
    import socket

    from pbd.security.network import offline

    backlog, package = artifacts
    fake = FakeAzure(namespace=NS)
    with offline():
        plan = _approved(backlog, package, fake, tmp_path)
        receipt = publish.verify(plan, publish.apply(plan, fake, MOCK, tmp_path / "j.jsonl"), fake)
        with pytest.raises(ConnectionError):  # the guard refuses any connection
            socket.create_connection(("127.0.0.1", 9))
    assert receipt["verification"]["status"] == "MOCK_VERIFIED"


def test_package_from_an_existing_backlog_then_mock_round_trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """D8 (corrective R5): an evolved or refined backlog.json gets the same local package finalize
    writes, then follows the unchanged approval-gated mock workflow. Nothing reaches a tracker."""
    from pbd.cli import main
    from pbd.pipeline.finalize import finalize
    from pbd.pipeline.review import submit_review
    from tests.pipeline.library_fixture import designed_run, review_payload

    run = designed_run(tmp_path / "lib", formats=["md"], title="Biblioteca")
    submit_review(run, review_payload(run))
    finalize(run)
    backlog = str(run.path("output/backlog.json"))
    out = str(tmp_path / "o")
    assert main(["azure", "package", "--backlog", backlog, "--out", out]) != 0  # profile is required
    assert main(["azure", "package", "--backlog", backlog, "--profile", "azure-agile", "--out", out]) == 0
    package = f"{out}/azure-import.json"
    pkg = json.loads(Path(package).read_text(encoding="utf-8"))
    assert len(pkg["work_items"]) == len(json.loads(Path(backlog).read_text(encoding="utf-8"))["items"])
    target = {"organization": "fabrikam-mock", "project": "backlog-mock"}
    empty = {"kind": "pbd.azure-snapshot", "target": target, "pages": [{"value": []}]}
    (tmp_path / "s.json").write_text(json.dumps(empty), encoding="utf-8")
    assert main(["azure", "prepare", "--backlog", backlog, "--package", package, "--snapshot",
                 str(tmp_path / "s.json"), "--target", NS, "--out", out]) == 0  # fmt: skip
    plan = f"{out}/publication-plan.json"
    assert main(["azure", "approve", "--plan", plan, "--target", NS, "--by", "owner", "--out", out]) == 0
    approved = f"{out}/publication-plan.approved.json"
    mock = str(tmp_path / "m.json")
    assert main(["azure", "apply", "--plan", approved, "--mock-state", mock, "--out", out]) == 0
    assert main(["azure", "verify", "--plan", approved, "--receipt", f"{out}/publication-receipt.json",
                 "--package", package, "--mock-state", mock, "--out", out]) == 0  # fmt: skip
    capsys.readouterr()


def test_normalized_snapshot_output_feeds_prepare(tmp_path: Path) -> None:
    """D9 (corrective R4b): `azure snapshot` output must be usable by `prepare`; tampering is refused."""
    from pbd.integrations.azure.snapshot import SnapshotError, load_snapshot

    raw = tmp_path / "export.json"
    raw.write_text(json.dumps({"count": 0, "value": []}), encoding="utf-8")
    normalized = load_snapshot(raw, {"organization": "clube", "project": "quadras"})
    norm_file = tmp_path / "azure-snapshot.normalized.json"
    norm_file.write_text(json.dumps(normalized), encoding="utf-8")
    again = load_snapshot(norm_file)
    assert again["target"]["namespace"] == "clube/quadras" and again["items"] == []
    normalized["items"].append({"id": 1})
    norm_file.write_text(json.dumps(normalized), encoding="utf-8")
    with pytest.raises(SnapshotError, match="content digest mismatch"):
        load_snapshot(norm_file)
