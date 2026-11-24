"""Test-wide offline boundary: every test runs with outbound network blocked.

Loopback is permitted only for future localhost mocks. Any attempt to reach a non-loopback
host fails the test immediately (NetworkBlocked) and is recorded; the fixture also asserts
the outer ledger stayed empty so a swallowed exception cannot hide an attempt.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pbd.security.network import offline

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_network() -> Iterator[None]:
    with offline(allow_localhost=True) as ledger:
        yield
    assert ledger.blocked == [], f"test attempted remote network access: {ledger.blocked}"


def load_valid(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (FIXTURES / "schemas" / "valid" / f"{name}.json").read_text(encoding="utf-8")
    )
    return data


@pytest.fixture
def backlog() -> dict[str, Any]:
    return copy.deepcopy(load_valid("backlog"))
