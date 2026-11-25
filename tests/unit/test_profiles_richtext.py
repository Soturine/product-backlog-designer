from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbd.profiles import (
    ProfileError,
    builtin_profiles,
    has_acceptance_field,
    load_profile,
    native_type,
    validate_profile,
)
from pbd.render.richtext import (
    RichTextError,
    criteria_html,
    criterion_sentence,
    description_html,
    inline,
    strip_html,
    validate_content,
)


def test_builtin_profiles_are_valid() -> None:
    profiles = builtin_profiles()
    assert set(profiles) == {"generic", "azure-agile", "azure-scrum", "azure-basic", "azure-cmmi"}
    for profile in profiles.values():
        assert validate_profile(profile) == [], profile["id"]


def test_profile_mapping_semantics() -> None:
    agile, basic, scrum = (
        load_profile("azure-agile"),
        load_profile("azure-basic"),
        load_profile("azure-scrum"),
    )
    assert (
        native_type(agile, "story") == "User Story" and native_type(scrum, "story") == "Product Backlog Item"
    )
    assert native_type(basic, "feature") is None
    assert has_acceptance_field(agile, "story") and not has_acceptance_field(agile, "task")
    assert not has_acceptance_field(basic, "story")
    assert agile["verified"] is False  # defaults are not proof of a target configuration


def test_custom_profile_file_validated(tmp_path: Path) -> None:
    custom = dict(load_profile("generic"), id="team-x", name="Team X")
    path = tmp_path / "p.json"
    path.write_text(json.dumps(custom), encoding="utf-8")
    assert load_profile(str(path))["id"] == "team-x"
    path.write_text(json.dumps({**custom, "types": {"epic": "Epic"}}), encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile(str(path))
    with pytest.raises(ProfileError):
        load_profile("does-not-exist")
    bad = {**custom, "fields": {**custom["fields"], "acceptance": None}}
    assert validate_profile(bad)


def test_story_prefixes_bold_per_language() -> None:
    content = {
        "kind": "role_goal_benefit",
        "actor": "membro",
        "want": "reservar um canteiro",
        "benefit": "cultivar",
    }
    pt = description_html(content, "pt-BR")
    assert pt.startswith("<p><strong>Eu como</strong> membro, <strong>gostaria que</strong> reservar")
    assert "<strong>para</strong> cultivar.</p>" in pt
    en = description_html(content, "en")
    assert "<strong>As a</strong>" in en and "<strong>so that</strong>" in en
    assert "<strong>Como</strong>" in description_html(content, "es-MX")


def test_structured_epic_task_enabler_spike() -> None:
    epic = description_html(
        {"kind": "epic", "objective": "Organizar", "in_scope": ["A", "B"], "out_scope": "Pagamentos"}, "pt-BR"
    )
    assert "<strong>No escopo</strong></p><ul><li>A</li><li>B</li></ul>" in epic
    assert "<strong>Fora do escopo</strong></p><ul><li>Pagamentos</li></ul>" in epic
    task = description_html(
        {"kind": "task", "summary": "Validar", "activities": ["x"], "verification": "y"}, "en"
    )
    assert "<strong>Activities</strong>" in task and "<strong>Verification</strong>: y" in task
    assert "Technical capability" in description_html(
        {"kind": "enabler", "capability": "c", "outcome": "o"}, "en"
    )
    assert "Question to answer" in description_html({"kind": "spike", "question": "q", "decision": "d"}, "en")


@pytest.mark.parametrize(
    "content",
    [
        {"kind": "role_goal_benefit", "actor": "", "want": "w", "benefit": "b"},
        {"kind": "epic"},
        {"kind": "task", "summary": "s", "invented": "x"},
        {"kind": "unknown"},
        {"kind": "task", "summary": "s", "activities": ["ok", ""]},
        "not an object",
    ],
)
def test_invalid_content_rejected(content: object) -> None:
    assert validate_content(content)
    if isinstance(content, dict):
        with pytest.raises(RichTextError):
            description_html(content, "en")


def test_inline_escapes_and_allows_only_safe_markup() -> None:
    assert inline("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert inline("**negrito** e [doc](https://example.com/a?b=1&c=2)") == (
        '<strong>negrito</strong> e <a href="https://example.com/a?b=1&amp;c=2">doc</a>'
    )
    assert "<a" not in inline("[x](javascript:alert(1))")
    assert "<a" not in inline('[x](https://e.com/"onmouseover="alert(1))') or 'onmouseover="' not in inline(
        '[x](https://e.com/"onmouseover="alert(1))'
    )
    assert inline("ação — çã") == "ação — çã"


CRITS = [
    {
        "visible_id": "CA-01",
        "condition": "canteiro livre",
        "trigger": "membro solicita",
        "expected_outcomes": ["reserva criada", "canteiro indisponível"],
    },
    {
        "visible_id": "CA-02",
        "text": "Canteiro ocupado não aceita reserva.",
        "expected_outcomes": ["nenhuma reserva"],
    },
]


def test_criteria_styles_render_same_meaning() -> None:
    lst, table, gherkin = (criteria_html(CRITS, s, "pt-BR") for s in ("list", "table", "gherkin"))
    assert lst.count("<li>") == 2 and "CA-01" in lst
    assert "<th>Critério de aceite</th><th>Resultado esperado</th>" in table and table.count("<tr>") == 3
    assert (
        "<strong>Dado</strong> canteiro livre" in gherkin
        and "<strong>E</strong> canteiro indisponível" in gherkin
    )
    for rendered in (lst, table, gherkin):
        plain = strip_html(rendered)
        for outcome in ("reserva criada", "canteiro indisponível", "nenhuma reserva"):
            assert outcome in plain or outcome in plain.replace("\n", " ")
    assert criteria_html([], "list", "en") == ""
    assert (
        criterion_sentence(CRITS[0])
        == "canteiro livre, membro solicita: reserva criada; canteiro indisponível"
    )


def test_duplicated_prefixes_are_not_repeated() -> None:
    """Regression (dogfood c10/c09): agent text that already starts with the label is not prefixed twice."""
    job = description_html(
        {
            "kind": "job_story",
            "situation": "Quando um pedido fica sem resposta",
            "motivation": "quero que ele seja cancelado",
            "outcome": "para que o item volte.",
        },
        "pt-BR",
    )
    assert "Quando</strong> um pedido" in job and "Quando Quando" not in job
    assert "quero</strong> que ele" in job and "quero quero" not in job
    assert "para que</strong> o item volte." in job
    story = description_html(
        {
            "kind": "role_goal_benefit",
            "actor": "Eu como membro",
            "want": "reservar",
            "benefit": "para cultivar",
        },
        "pt-BR",
    )
    assert "<strong>Eu como</strong> membro," in story and "<strong>para</strong> cultivar." in story
