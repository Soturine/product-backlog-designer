from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbd.core.canonical import digest
from pbd.persistence import atomic
from pbd.persistence.atomic import Journal, JournalError, atomic_write_bytes, atomic_write_json
from pbd.persistence.state import RunState, StateError
from pbd.validation.schema import validate

D1, D2, D3 = digest("a"), digest("b"), digest("c")


def test_atomic_write_replaces_content(tmp_path: Path) -> None:
    target = tmp_path / "x" / "f.json"
    atomic_write_json(target, {"b": 1, "a": "ç"})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": "ç", "b": 1}
    assert target.read_bytes().startswith(b'{\n  "a"')
    atomic_write_json(target, {"v": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 2}
    assert [p.name for p in target.parent.iterdir()] == ["f.json"]


def test_atomic_write_failure_keeps_old_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "f.txt"
    target.write_bytes(b"old")

    def boom(*_: object) -> None:
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(atomic.os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["f.txt"]  # temp file cleaned up


def test_journal_chain_and_tamper_detection(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "j.jsonl")
    journal.append("a", {"n": 1})
    journal.append("b", {"n": 2})
    head = journal.verify()
    assert head.startswith("sha256:") and len(journal.entries()) == 2

    lines = journal.path.read_bytes().splitlines()
    tampered = lines[0].replace(b'"n":1', b'"n":9')
    journal.path.write_bytes(b"\n".join([tampered, lines[1]]) + b"\n")
    with pytest.raises(JournalError):
        journal.verify()
    tampered_bytes = journal.path.read_bytes()
    with pytest.raises(JournalError):
        journal.append("c", {"n": 3})  # refuses to extend a broken chain
    assert journal.path.read_bytes() == tampered_bytes


def test_journal_detects_reorder_and_torn_line(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "j.jsonl")
    for i in range(3):
        journal.append("e", {"i": i})
    lines = journal.path.read_bytes().splitlines()
    journal.path.write_bytes(b"\n".join([lines[1], lines[0], lines[2]]) + b"\n")
    with pytest.raises(JournalError):
        journal.verify()
    journal.path.write_bytes(b"\n".join(lines) + b'\n{"seq": 3, "prev"')
    with pytest.raises(JournalError):
        journal.verify()
    with pytest.raises(JournalError):
        journal.append("x", {})


def _complete_chain(state: RunState) -> None:
    for name in ["inventory", "reading", "claims", "design", "independent_review", "gates", "render"]:
        state.complete(name, D1, D2)


def test_run_state_roundtrip_and_schema(tmp_path: Path) -> None:
    state = RunState.create(tmp_path, "generate", synthetic=True)
    assert validate("run-manifest", state.manifest) == []
    loaded = RunState.load(tmp_path)
    assert loaded.manifest["run_id"] == state.manifest["run_id"]
    assert loaded.manifest["network"] == {"mode": "offline", "remote_calls": 0}
    assert loaded.manifest["status"]["remote_state"] == "not_contacted"


def test_stage_requires_dependencies(tmp_path: Path) -> None:
    state = RunState.create(tmp_path, "generate")
    with pytest.raises(StateError):
        state.complete("claims", D1, D2)
    assert RunState.load(tmp_path).stage("claims")["status"] == "pending"
    assert len(state.journal.entries()) == 1  # only run_created; rejection not journaled as completion


def test_changed_output_invalidates_transitive_dependents(tmp_path: Path) -> None:
    state = RunState.create(tmp_path, "generate")
    _complete_chain(state)
    assert state.complete("reading", D1, D2) == []  # same output: nothing invalidated
    invalidated = state.complete("reading", D1, D3)
    assert set(invalidated) == {"claims", "design", "independent_review", "gates", "render"}
    assert state.stage("inventory")["status"] == "complete"
    reloaded = RunState.load(tmp_path)
    assert reloaded.stage("render")["status"] == "invalidated"
    assert "reading" in reloaded.stage("render")["invalidated_reason"]
    assert not reloaded.is_reusable("claims", D1)
    assert reloaded.is_reusable("reading", D1)


def test_source_change_or_addition_invalidates_everything_downstream(tmp_path: Path) -> None:
    state = RunState.create(tmp_path, "generate")
    src = {
        "source_id": "PBD-SRC-000000000001",
        "selector": "a.md",
        "authority": "functional",
        "digest": D1,
        "reader": {"status": "complete", "independence": "sequential_role"},
    }
    state.register_source(src)
    _complete_chain(state)
    assert state.register_source(dict(src)) == []  # unchanged digest
    changed = state.register_source({**src, "digest": D2})
    assert "inventory" in changed and "render" in changed
    _complete_chain(state)
    added = state.register_source({**src, "source_id": "PBD-SRC-000000000002", "selector": "b.md"})
    assert "inventory" in added and "independent_review" in added


def test_load_rejects_tampered_journal(tmp_path: Path) -> None:
    state = RunState.create(tmp_path, "generate")
    state.journal.path.write_bytes(state.journal.path.read_bytes().replace(b"generate", b"audit"))
    with pytest.raises(JournalError):
        RunState.load(tmp_path)


def test_save_refuses_invalid_manifest(tmp_path: Path) -> None:
    state = RunState.create(tmp_path, "generate")
    before = state.manifest_path.read_bytes()
    state.manifest["network"]["remote_calls"] = 1
    with pytest.raises(StateError):
        state.save()
    assert state.manifest_path.read_bytes() == before  # nothing written on rejection


def test_journal_detects_entry_spliced_from_another_journal(tmp_path: Path) -> None:
    # Regression (mutation pass): each entry's digest and seq stay valid after a cross-journal
    # splice, so only the prev-link check detects it.
    a, b = Journal(tmp_path / "a.jsonl"), Journal(tmp_path / "b.jsonl")
    for j, tag in ((a, "a"), (b, "b")):
        j.append("e", {"tag": tag, "n": 0})
    a.append("e", {"tag": "a", "n": 1})
    b.append("e", {"tag": "b", "n": 1})
    a_lines = a.path.read_bytes().splitlines()
    b_lines = b.path.read_bytes().splitlines()
    a.path.write_bytes(b"\n".join([a_lines[0], b_lines[1]]) + b"\n")
    with pytest.raises(JournalError, match="chain broken"):
        a.verify()
