"""Payloads must be UTF-8; a cp1252 file gets an actionable error, never a silent re-decode."""

from __future__ import annotations

import pytest

from pbd.core.canonical import CanonicalError, loads_strict


def test_cp1252_payload_is_refused_with_guidance() -> None:
    with pytest.raises(CanonicalError, match=r"not UTF-8.*encoding='utf-8'"):
        loads_strict('{"t": "aprovação"}'.encode("cp1252"))
    assert loads_strict('{"t": "aprovação"}'.encode()) == {"t": "aprovação"}
    assert loads_strict(b"\xef\xbb\xbf" + b'{"a": 1}') == {"a": 1}
