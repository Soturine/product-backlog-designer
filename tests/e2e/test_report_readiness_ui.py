"""Browser tests of the readiness, gate-explanation, appearance and table controls (schema 1.2.0).

Uses the second synthetic domain (library kiosk) where one blocking question blocks one task.
Every non-file request is aborted and recorded (offline proof). Skipped when no system browser.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.finalize import finalize
from pbd.pipeline.review import submit_review
from tests.e2e.test_report_browser import _open, browser  # noqa: F401  (fixture re-export)
from tests.pipeline.library_fixture import designed_run, review_payload

pytestmark = pytest.mark.playwright


@pytest.fixture(scope="module")
def lib(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    run = designed_run(
        tmp_path_factory.mktemp("lib"), formats=["azure"], profile="azure-agile", title="Biblioteca"
    )
    submit_review(run, review_payload(run))
    finalize(run)
    backlog = json.loads(run.path("output/backlog.json").read_text(encoding="utf-8"))
    return run.path("output/report.html"), backlog


def _blocked(backlog: dict[str, Any]) -> dict[str, Any]:
    return next(i for i in backlog["items"] if (i.get("readiness") or {}).get("status") == "blocked")


def test_overview_counts_readiness_from_canonical_data(browser: Any, lib: Any) -> None:  # noqa: F811
    path, backlog = lib
    page, external, errors = _open(browser, path)
    buildable = [i for i in backlog["items"] if i["type"] not in ("epic", "feature")]
    cells = page.locator(".rdy-grid a").all_inner_texts()
    want = {
        s: sum(1 for i in buildable if i["readiness"]["status"] == s) for s in ("ready", "partial", "blocked")
    }
    assert any(f"{want['ready']}/{len(buildable)}" in c for c in cells)
    assert any(f"{want['blocked']}/{len(buildable)}" in c for c in cells)
    # the blocking question names exactly the work it blocks
    decision = page.locator(".decisions li").first.inner_text()
    assert _blocked(backlog)["title"] in decision
    assert external == [] and errors == []


def test_readiness_filter_and_blocked_detail(browser: Any, lib: Any) -> None:  # noqa: F811
    path, backlog = lib
    page, _, errors = _open(browser, path, "#backlog")
    page.select_option("#f-readiness", "blocked")
    visible = [x for x in page.locator("#tree li[data-id]").all() if x.is_visible()]
    matched = [x.get_attribute("data-id") for x in visible if x.get_attribute("data-readiness") == "blocked"]
    assert matched == [_blocked(backlog)["id"]]
    page.goto(path.as_uri() + "#item-" + _blocked(backlog)["id"])
    art = page.locator(f"article#item-{_blocked(backlog)['id']}")
    text = art.inner_text()
    q = next(q for q in backlog["questions"] if q["blocking"])
    assert q["text"] in text
    assert art.locator(f"#rd-{_blocked(backlog)['id']} a[href='#q-{q['id']}']").count() == 1
    assert errors == []


def test_appearance_switch_is_presentation_only(browser: Any, lib: Any) -> None:  # noqa: F811
    path, backlog = lib
    page, external, errors = _open(browser, path, "#backlog")
    assert page.get_attribute("html", "data-appearance") == "azure"  # azure-agile target
    page.select_option("#f-type", "task")
    before_json = page.locator("#canonical").text_content()
    for ap in ("jira", "generic", "azure"):
        page.select_option("#appearance-sel", ap)
        assert page.get_attribute("html", "data-appearance") == ap
        hrefs = page.eval_on_selector_all("svg.ti > use", "els => els.map(e => e.getAttribute('href'))")
        assert hrefs and all(h.startswith(f"#t-{ap}-") for h in hrefs)
    # filters, selection state and canonical data survive the switch; the target profile is unchanged
    assert page.input_value("#f-type") == "task"
    assert page.locator("#canonical").text_content() == before_json
    assert backlog["profile"] == "azure-agile"
    # the preference persists in the session
    page.reload()
    assert page.get_attribute("html", "data-appearance") == "azure"
    page.select_option("#appearance-sel", "jira")
    page.reload()
    assert page.get_attribute("html", "data-appearance") == "jira"
    # every type label stays available as text to assistive technology
    assert page.locator("#tree li[data-id] > .row > a.lbl > .sr-only").count() == len(backlog["items"])
    assert external == [] and errors == []


def test_table_sort_reset_and_column_visibility(browser: Any, lib: Any) -> None:  # noqa: F811
    path, _ = lib
    page, _, errors = _open(browser, path, "#backlog")
    page.click(".seg [data-xview='table']")
    keys = lambda: page.eval_on_selector_all(  # noqa: E731
        "#itable tbody tr td:first-child", "els => els.map(e => e.textContent)"
    )
    original = keys()
    page.click("button.sort[data-sort='readiness']")
    assert page.get_attribute("th[data-col='readiness']", "aria-sort") == "ascending"
    statuses = page.eval_on_selector_all(
        "#itable tbody tr",
        "rows => { const i = [...document.querySelectorAll('#itable thead th')]"
        ".findIndex(th => th.dataset.col === 'readiness'); return rows.map(r => r.cells[i].dataset.v); }",
    )
    known = [s for s in statuses if s]
    assert known == sorted(known) and statuses[-1] == ""  # unknown (containers) always last
    page.click("#sort-reset")
    assert keys() == original
    page.click(".colpick summary")
    page.uncheck("[data-colvis='verdict']")
    assert not page.locator("th[data-col='verdict']").is_visible()
    assert errors == []


def test_gate_explanation_shows_purpose_status_and_affected_work(browser: Any, lib: Any) -> None:  # noqa: F811
    path, backlog = lib
    page, _, errors = _open(browser, path, "#gate-G06")
    g = page.locator("details#gate-G06")
    assert g.get_attribute("open") is not None
    text = g.inner_text()
    assert "Por que importa" in text and "Tipo de evidência" in text
    # the gate-tagged finding's affected criterion is linked with its story context
    crit = next(c for c in backlog["criteria"] if c.get("status") == "proposed")
    affected = g.locator("dl.gate-help dd").filter(has=page.locator(f"a[href='#crit-{crit['id']}']"))
    assert affected.count() >= 1
    # the raw runtime message is kept but behind the technical disclosure
    assert not g.locator("details.tech-gate code").first.is_visible()
    g2 = page.locator("details#gate-G02")
    page.goto(path.as_uri() + "#gate-G02")
    assert "tratadas segundo G02" in g2.inner_text()
    assert errors == []


def test_mobile_drawer_exposes_appearance_and_theme_by_keyboard(browser: Any, lib: Any) -> None:  # noqa: F811
    path, _ = lib
    page, external, errors = _open(browser, path, "#backlog", viewport={"width": 390, "height": 844})
    assert not page.locator("#appearance-sel").is_visible()  # header control hidden on small screens
    page.click("#menu")
    m = page.locator("#appearance-sel-m")
    assert m.is_visible() and page.locator("label[for='appearance-sel-m']").is_visible()
    m.focus()
    page.keyboard.press("End")  # keyboard-only choice of the last option (Jira)
    page.wait_for_timeout(100)
    assert page.get_attribute("html", "data-appearance") == "jira"
    page.select_option("#theme-sel-m", "dark")
    assert page.get_attribute("html", "data-theme") == "dark"
    page.keyboard.press("Escape")  # drawer closes, focus returns to the menu button
    assert page.evaluate("document.activeElement.id") == "menu"
    assert external == [] and errors == []
