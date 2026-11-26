from __future__ import annotations

import copy
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from pbd.core.canonical import digest
from pbd.integrations.authority import (
    AuthorizationDenied,
    RemoteAuthority,
    authorize_apply,
    plan_content_digest,
)
from pbd.security.network import NetworkBlocked, offline
from pbd.security.privacy import scan_paths, scan_text
from tests.conftest import REPO_ROOT, load_valid

pytestmark = pytest.mark.security


# ---------- zero-network default -------------------------------------------------
@pytest.mark.parametrize("host", ["192.0.2.10", "dev.azure.com", "example.invalid", "2001:db8::1"])
def test_offline_blocks_remote_hosts(host: str) -> None:
    with offline() as ledger, pytest.raises(NetworkBlocked):
        socket.create_connection((host, 443), timeout=0.1)
    with offline() as ledger2, pytest.raises(NetworkBlocked):
        socket.getaddrinfo(host, 443)
    assert host in ledger.blocked and host in ledger2.blocked


def test_offline_blocks_raw_socket_connect() -> None:
    with offline():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(NetworkBlocked):
                s.connect(("198.51.100.7", 80))
            with pytest.raises(NetworkBlocked):
                s.connect_ex(("198.51.100.7", 80))
        finally:
            s.close()


def test_loopback_blocked_by_default_and_allowed_only_on_opt_in() -> None:
    with offline(), pytest.raises(NetworkBlocked):
        socket.getaddrinfo("localhost", 80)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        with offline(allow_localhost=True) as ledger:
            client = socket.create_connection(("127.0.0.1", port), timeout=2)
            client.close()
        assert "127.0.0.1" in ledger.allowed_local and not ledger.blocked
    finally:
        server.close()


def test_offline_restores_socket_functions() -> None:
    before = (socket.socket.connect, socket.getaddrinfo, socket.create_connection)
    with offline():
        pass
    assert (socket.socket.connect, socket.getaddrinfo, socket.create_connection) == before


# ---------- privacy scanner ------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("-----BEGIN RSA " + "PRIVATE KEY-----", "private_key"),
        ("key = AKIA" + "ABCDEFGHIJKLMNOP", "aws_access_key"),
        ("token ghp_" + "a" * 36, "github_token"),
        ("Authorization: Bearer " + "abcdefghijklmnopqrstuvwx", "bearer_token"),
        ("AZURE_DEVOPS_EXT_PAT=" + "a" * 52, "azure_pat_assignment"),
        ('password = "' + "hunter2hunter2" + '"', "generic_secret_assignment"),
        ("contato: fulano@" + "empresa-real.com.br", "email_address"),
        ("https://dev.azure.com/" + "acme-corp/proj", "tracker_org_url"),
        ("https://" + "acmecorp.visualstudio.com/x", "tracker_org_url"),
    ],
)
def test_privacy_scanner_detects(text: str, rule: str) -> None:
    findings = scan_text(text)
    assert rule in {f.rule for f in findings}
    assert all(text not in str(f) for f in findings)  # never echoes the secret


@pytest.mark.parametrize(
    "text",
    [
        "membro@example.com",
        "1234+user@users.noreply.github.com",
        "https://dev.azure.com/{organization}/_apis",
        "https://learn.microsoft.com/en-us/rest/api/azure/devops/",
        "password: <not stored>",
        "https://marketplace.visualstudio.com/items?itemName=publisher.extension",
    ],
)
def test_privacy_scanner_allows_documentation_placeholders(text: str) -> None:
    assert scan_text(text) == []


def test_repository_tracked_files_are_privacy_clean() -> None:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        pytest.skip(f"git unavailable: {exc}")
    paths = [REPO_ROOT / line for line in out.splitlines() if line]
    findings = scan_paths(paths, REPO_ROOT)
    assert findings == [], "\n".join(map(str, findings))


# ---------- remote-write authorization boundary -----------------------------------
def _approved_plan() -> dict[str, Any]:
    plan = copy.deepcopy(load_valid("publication-plan"))
    plan["plan_digest"] = plan_content_digest(plan)
    plan["approval"] = {
        "state": "approved",
        "approved_plan_digest": plan["plan_digest"],
        "approved_target_namespace": "fixture-project",
        "approved_by": "fixture-owner",
        "approved_at": "2026-11-24T12:00:00Z",
    }
    return plan


def assert_denied(
    plan: dict[str, Any], authority: RemoteAuthority, target: str, match: str | None = None
) -> None:
    """Denial must raise AND leave the plan (including its approval) untouched."""
    before = copy.deepcopy(plan)
    with pytest.raises(AuthorizationDenied, match=match):
        authorize_apply(plan, authority, target)
    assert plan == before


MOCK = RemoteAuthority(opted_in=True, transport="mock")


def test_valid_mock_authorization_passes() -> None:
    import copy

    plan = _approved_plan()
    before = copy.deepcopy(plan)
    # success is the absence of AuthorizationDenied; authorizing must never alter the approved plan
    assert authorize_apply(plan, MOCK, "fixture-project") is None  # type: ignore[func-returns-value]
    assert plan == before


@pytest.mark.parametrize(
    "authority",
    [
        RemoteAuthority(),
        RemoteAuthority(opted_in=False, transport="mock"),
        RemoteAuthority(opted_in=True, transport="none"),
        RemoteAuthority(opted_in=True, transport="live"),
        RemoteAuthority(opted_in=True, transport="carrier-pigeon"),
    ],
)
def test_denied_without_authority_or_live_transport(authority: RemoteAuthority) -> None:
    assert_denied(_approved_plan(), authority, "fixture-project")


def test_denied_when_unapproved() -> None:
    plan = _approved_plan()
    plan["approval"] = {"state": "unapproved"}
    assert_denied(plan, MOCK, "fixture-project", match="not approved")


def test_denied_when_plan_edited_after_approval() -> None:
    plan = _approved_plan()
    plan["operations"][0]["fields"]["System.Title"] = "alterado depois da aprovação"
    assert_denied(plan, MOCK, "fixture-project", match="stale plan")


def test_denied_when_approval_is_for_other_digest() -> None:
    plan = _approved_plan()
    plan["approval"]["approved_plan_digest"] = digest("older plan")
    assert_denied(plan, MOCK, "fixture-project", match="stale approval")


def test_denied_for_wrong_target() -> None:
    assert_denied(_approved_plan(), MOCK, "another-project", match="target")


def test_denied_with_unresolved_conflict() -> None:
    plan = _approved_plan()
    plan["operations"].append(
        {
            "op_id": "PBD-OP-000000000009",
            "action": "CONFLICT",
            "pbd_id": plan["operations"][0]["pbd_id"],
            "reason": "revision changed remotely",
        }
    )
    plan["plan_digest"] = plan_content_digest(plan)
    plan["approval"]["approved_plan_digest"] = plan["plan_digest"]
    assert_denied(plan, MOCK, "fixture-project", match="conflict")


def test_no_live_transport_module_exists() -> None:
    src = REPO_ROOT / "src" / "pbd"
    forbidden = ("requests", "httpx", "urllib.request", "http.client", "azure.devops", "subprocess")
    offenders = [
        f"{p.relative_to(REPO_ROOT)}:{name}"
        for p in src.rglob("*.py")
        for name in forbidden
        if f"import {name}" in p.read_text(encoding="utf-8")
        or f"from {name}" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_privacy_scan_cli_counts_files(tmp_path: Path) -> None:
    from pbd.cli import main

    (tmp_path / "a.md").write_text("ok", encoding="utf-8")
    assert main(["privacy-scan", ".", "--root", str(tmp_path)]) == 0
    (tmp_path / "b.md").write_text("AKIA" + "ABCDEFGHIJKLMNOP", encoding="utf-8")
    assert main(["privacy-scan", ".", "--root", str(tmp_path)]) == 1
