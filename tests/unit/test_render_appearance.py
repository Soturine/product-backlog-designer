"""Appearance icons, prose key links and reviewer-prose references (CP2, QL-004 residual)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pbd.pipeline.design import submit_claims, submit_design
from pbd.pipeline.review import validate_review
from pbd.pipeline.run import normalize_request, start
from pbd.render.icons import APPEARANCES, GLYPHS, TYPES, appearance_for_profile, sprite, type_icon
from pbd.render.report_html import R
from tests.pipeline.helpers import claims_payload, design_payload, make_workspace, read_all
from tests.pipeline.test_review_finalize import review_payload


def test_every_appearance_has_every_type_and_a_neutral_fallback() -> None:
    for ap in APPEARANCES:
        assert set(GLYPHS[ap]) == {*TYPES, "unknown"}
    assert 'href="#t-jira-unknown"' in type_icon("custom<script>", "jira")
    assert "<script" not in type_icon("custom<script>", "jira")


def test_sprite_is_static_markup_without_active_content() -> None:
    markup = sprite()
    for bad in ("<script", "href=", "xlink", "style=", "on", "url(", "<image", "<foreignObject"):
        if bad == "on":
            assert not re.search(r"\son[a-z]+=", markup)
        else:
            assert bad not in markup
    assert markup.count("<symbol") == sum(len(GLYPHS[a]) for a in APPEARANCES)


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("azure-agile", "azure"),
        ("azure-scrum", "azure"),
        ("generic", "generic"),
        (None, "generic"),
        ("jira-x", "jira"),
    ],
)
def test_default_appearance_follows_the_known_target(profile: str | None, expected: str) -> None:
    assert appearance_for_profile(profile) == expected


def test_prose_links_only_known_keys_and_escapes_everything_else() -> None:
    r = R("pt-BR", {"PBD-AC-000000000001": "AC7"})
    r.links["AC7"] = ("crit-PBD-AC-000000000001", "CA-01 · Story <b>")
    html = r.prose("Responder Q2 e atualizar AC7. <img src=x onerror=alert(1)> AC70 xAC7")
    assert html.count("<a ") == 1
    assert 'href="#crit-PBD-AC-000000000001"' in html and 'title="CA-01 · Story &lt;b&gt;"' in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "AC70" in html and "xAC7" in html  # partial tokens are never linked


def test_reviewer_prose_rejects_visible_criterion_ids_but_not_design_keys(tmp_path: Path) -> None:
    ws = make_workspace(tmp_path)
    run = start(
        tmp_path / "out",
        ws,
        [("prd.md", "functional"), ("decisoes", "decision")],
        normalize_request(synthetic=True),
    )
    read_all(run)
    submit_claims(run, claims_payload(run))
    submit_design(run, design_payload())
    review = review_payload(run)
    review["findings"][0]["recommendation"] = "Responder Q1 e revisar AC2 de US1."  # design keys resolve
    assert validate_review(run, review) == []
    review["findings"][0]["recommendation"] = "Revisar o CA-02."  # repeats in every story
    errors = validate_review(run, review)
    assert any("findings[0].recommendation: cites visible criterion ID CA-02" in e for e in errors)
    review = review_payload(run)
    review["items"][2]["notes"] = "AC-01 vago"
    assert any("visible criterion ID AC-01" in e for e in validate_review(run, review))
    # verbatim source quotes may contain ID-like text and are never checked
    review = review_payload(run)
    review["independent_obligations"][0]["text"] = "CA-01 no texto da obrigação"
    assert validate_review(run, review) == []
