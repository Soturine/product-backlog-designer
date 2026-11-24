from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pbd.core.canonical import CanonicalError, canonical_bytes, digest, loads_strict
from pbd.core.identity import KINDS, ExternalRef, IdentityError, derive, is_pbd_id, kind_of, mint

json_scalars = (
    st.none()
    | st.booleans()
    | st.integers(-(2**53), 2**53)
    | st.text(max_size=20)
    | st.floats(allow_nan=False, allow_infinity=False)
)
json_values = st.recursive(
    json_scalars,
    lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=8), c, max_size=4),
    max_leaves=20,
)


# ---------- identity -------------------------------------------------------
@pytest.mark.parametrize("kind", sorted(KINDS))
def test_mint_produces_valid_opaque_ids(kind: str) -> None:
    ident = mint(kind)
    assert is_pbd_id(ident)
    assert kind_of(ident) == kind


def test_mint_is_unique() -> None:
    assert len({mint("story") for _ in range(2000)}) == 2000


def test_derive_is_deterministic_and_order_independent() -> None:
    a = derive("claim", {"source": "PBD-SRC-000000000001", "locator": "s2 l12"})
    b = derive("claim", {"locator": "s2 l12", "source": "PBD-SRC-000000000001"})
    assert a == b and is_pbd_id(a)
    assert derive("claim", {"source": "PBD-SRC-000000000001", "locator": "s2 l13"}) != a


def test_derive_separates_kinds() -> None:
    anchor = {"source": "x", "locator": "y"}
    assert derive("story", anchor).split("-")[2] != derive("task", anchor).split("-")[2]


@pytest.mark.parametrize("bad", ["title", "Title", "position", "index", "order", "name"])
def test_derive_rejects_title_or_position_anchors(bad: str) -> None:
    with pytest.raises(IdentityError):
        derive("story", {bad: "Reservar canteiro"})


def test_derive_rejects_empty_anchor_and_unknown_kind() -> None:
    with pytest.raises(IdentityError):
        derive("story", {})
    with pytest.raises(IdentityError):
        mint("sprint")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "PBD-STORY-short",
        "pbd-story-000000000001",
        "PBD-STORY-00000000000I",
        "PBD-XYZ-000000000001",
        None,
        42,
    ],
)
def test_is_pbd_id_rejects_malformed(value: object) -> None:
    assert not is_pbd_id(value)


def test_external_ref_namespace_is_separate() -> None:
    ref = ExternalRef("mock", "fixture-project", "1001", 3)
    assert ref.key() == ("mock", "fixture-project", "1001")
    with pytest.raises(IdentityError):
        ExternalRef("mock", "fixture-project", mint("task"))
    with pytest.raises(IdentityError):
        ExternalRef("", "ns", "1")


@settings(max_examples=200)
@given(st.text(min_size=1, max_size=60))
def test_property_ids_never_embed_titles(title: str) -> None:
    ident = derive("story", {"source": "s", "locator": title})
    assert is_pbd_id(ident)
    body = ident.rsplit("-", 1)[1]
    assert len(body) == 12


# ---------- canonical JSON -------------------------------------------------
def test_digest_independent_of_key_order_and_unicode_form() -> None:
    nfc = "ação"
    nfd = "ação"
    assert digest({"a": 1, "b": nfc}) == digest({"b": nfd, "a": 1})


def test_canonical_preserves_unicode_bytes() -> None:
    assert "ção".encode() in canonical_bytes({"t": "ção"})


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_rejected(bad: float) -> None:
    with pytest.raises(CanonicalError):
        canonical_bytes({"x": bad})


def test_unsupported_types_and_keys_rejected() -> None:
    with pytest.raises(CanonicalError):
        canonical_bytes({"x": {1, 2}})
    with pytest.raises(CanonicalError):
        canonical_bytes({1: "x"})


def test_loads_strict_rejects_duplicates_and_nan_accepts_bom() -> None:
    with pytest.raises(CanonicalError):
        loads_strict('{"a": 1, "a": 2}')
    with pytest.raises(CanonicalError):
        loads_strict('{"a": NaN}')
    assert loads_strict(b'\xef\xbb\xbf{"a": "\xc3\xa7"}') == {"a": "ç"}


@settings(max_examples=300)
@given(json_values)
def test_property_canonical_roundtrip_is_stable(value: object) -> None:
    once = canonical_bytes(value)
    assert canonical_bytes(loads_strict(once)) == once
    assert digest(loads_strict(once)) == digest(value)


@settings(max_examples=200)
@given(st.dictionaries(st.text(max_size=6), st.integers(), min_size=2, max_size=8))
def test_property_digest_ignores_insertion_order(mapping: dict[str, int]) -> None:
    reversed_mapping = dict(reversed(list(mapping.items())))
    assert digest(mapping) == digest(reversed_mapping)
