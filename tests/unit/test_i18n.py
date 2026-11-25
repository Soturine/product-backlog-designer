"""UI catalogs: parity, placeholders, plurals, enum coverage and no hardcoded English in other locales."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from pbd import vocab
from pbd.render.i18n import LOCALES, Translator, catalog, plural_category, resolve_locale

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _placeholders(value: object) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(PLACEHOLDER.findall(v) for v in value.values()))
    return set(PLACEHOLDER.findall(str(value)))


def test_catalogs_have_identical_keys_and_placeholders() -> None:
    base = catalog("en")
    for loc in LOCALES:
        cat = catalog(loc)
        assert set(cat) == set(base), (loc, sorted(set(cat) ^ set(base))[:10])
        for key, value in base.items():
            if key == "_meta":
                continue
            assert _placeholders(cat[key]) == _placeholders(value), (loc, key)
            assert isinstance(cat[key], type(value)), (loc, key)
            if isinstance(value, dict):
                assert {"one", "other"} <= set(cat[key]), (loc, key)
            else:
                assert str(cat[key]).strip(), (loc, key)


@pytest.mark.parametrize(
    ("group", "codes"),
    [
        ("verdict", vocab.VERDICTS),
        ("support", vocab.SOURCE_SUPPORT),
        ("rating", vocab.INVEST_RATINGS),
        ("task_suff", vocab.TASK_SUFFICIENCY),
        ("invest", vocab.INVEST_DIMENSIONS),
        ("classification", vocab.finding_classifications()),
        ("severity", vocab.finding_severities()),
        ("disposition", vocab.review_dispositions()),
        ("category", vocab.claim_categories()),
    ],
)
def test_every_canonical_code_has_a_label(group: str, codes: frozenset[str]) -> None:
    for loc in LOCALES:
        cat = catalog(loc)
        missing = [c for c in codes if f"enum.{group}.{c}" not in cat]
        assert not missing, (loc, group, missing)


def test_all_eighteen_gates_have_names() -> None:
    for loc in LOCALES:
        assert all(f"enum.gate.G{n:02d}" in catalog(loc) for n in range(1, 19))


def test_plurals_numbers_and_fallback() -> None:
    pt, en, es = Translator("pt-BR"), Translator("en"), Translator("es")
    assert pt("ov.blocking_q", n=0) == "Nenhuma pergunta bloqueante"
    assert pt("ov.blocking_q", n=1) == "1 pergunta bloqueante"
    assert pt("ov.blocking_q", n=1200) == "1.200 perguntas bloqueantes"
    assert en("ov.blocking_q", n=2) == "2 blocking questions"
    assert es("ex.count", n=1) == "1 elemento coincide"
    assert plural_category("pt-BR", 0) == "one" and plural_category("en", 0) == "other"
    assert pt("cmp.headline_cov", l=1, r=2, n=3) == "A esquerda cobre 1 e a direita cobre 2 de 3 obrigações."
    assert pt.enum("type", "unknown-code") == "unknown-code"  # unknown codes shown as-is, never guessed
    with pytest.raises(KeyError):
        pt("no.such.key")
    assert (
        resolve_locale("pt") == "pt-BR" and resolve_locale("es-AR") == "es" and resolve_locale("de") == "en"
    )


def test_pt_catalog_keeps_codes_but_translates_labels() -> None:
    pt = catalog("pt-BR")
    assert pt["enum.support.supported"] == "Fundamentado"
    assert pt["enum.severity.medium"] == "Média"
    assert pt["a11y.skip"] == "Ir para o conteúdo"
    assert pt["col.key"] == "Chave" and pt["col.rationale"] == "Justificativa"


class _Text(HTMLParser):
    """Visible UI text (skips content marked with a lang attribute, code, scripts and data)."""

    SKIP = frozenset({"script", "style", "code", "pre", "svg"})

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("br", "input", "meta", "link", "use", "rect", "path", "circle"):
            return
        a = dict(attrs)
        content = "lang" in a and tag != "html"
        mono = (
            "mono" in (a.get("class") or "")
            or "loc" in (a.get("class") or "")
            or "fref" in (a.get("class") or "")
        )
        parent_skip = self.stack[-1][1] if self.stack else False
        self.stack.append((tag, parent_skip or content or mono or tag in self.SKIP))

    def handle_endtag(self, tag: str) -> None:
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break

    def handle_data(self, data: str) -> None:
        if not (self.stack and self.stack[-1][1]) and data.strip():
            self.chunks.append(data.strip())


ENGLISH_LITERALS = {
    "verified",
    "supported",
    "medium",
    "profile",
    "key",
    "rationale",
    "gate",
    "skip to content",
    "sections",
    "covered by",
    "verdict",
    "type",
    "status",
    "claim",
    "notes",
    "proposed",
    "blocking",
    "review",
}


def test_portuguese_report_has_no_english_ui_literals(tmp_path: Path) -> None:
    from pbd.pipeline.finalize import finalize
    from pbd.pipeline.review import submit_review
    from tests.pipeline.helpers import designed_run
    from tests.pipeline.test_review_finalize import review_payload

    run = designed_run(tmp_path, formats=["azure"], profile="azure-agile", title="Horta")
    submit_review(run, review_payload(run))
    finalize(run)
    page = run.path("output/report.html").read_text(encoding="utf-8")
    parser = _Text()
    parser.feed(page)
    words = {c.lower() for c in parser.chunks}
    leaked = sorted(words & ENGLISH_LITERALS)
    assert not leaked, leaked
    assert 'lang="pt-BR"' in page and "Ir para o conteúdo" in page
    i18n = json.loads(re.search(r'id="pbd-i18n">(.*?)</script>', page, re.S).group(1))  # type: ignore[union-attr]
    assert set(i18n) == set(LOCALES)
