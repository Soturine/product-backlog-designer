"""Browser tests of report.html with the system Edge/Chrome via Playwright (no browser download).

Every request other than the file itself is aborted and recorded, proving the report is offline.
Skipped (not passed) when Playwright or a system browser is unavailable.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.finalize import finalize
from pbd.pipeline.review import submit_review
from tests.pipeline.helpers import designed_run
from tests.pipeline.test_review_finalize import review_payload

pytestmark = pytest.mark.playwright
sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    with sync_api.sync_playwright() as pw:
        for channel in ("msedge", "chrome"):
            try:
                b = pw.chromium.launch(channel=channel)
            except Exception:
                continue
            yield b
            b.close()
            return
        pytest.skip("no system Edge/Chrome available for Playwright")


def _report(tmp: Path, hostile: bool = False) -> Path:
    run = designed_run(tmp, formats=["azure"], profile="azure-agile", title="Horta — relatório")
    if hostile:
        draft = run.read("stages/backlog.draft.json")
        draft["items"][0]["title"] = (
            '<img src=x onerror="window.__xss=1">Épico <script>window.__xss=2</script>'
        )
        draft["items"][0]["description"]["value"] = (
            '<p>ok</p><script>window.__xss=3</script><a href="javascript:alert(1)">x</a>'
        )
        run.write_artifact("stages/backlog.draft.json", draft)
        run.save()
    submit_review(run, review_payload(run))
    finalize(run)
    return run.path("output/report.html")


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _report(tmp_path_factory.mktemp("rep"))


def _open(browser: Any, path: Path, **ctx: Any) -> tuple[Any, list[str], list[str]]:
    context = browser.new_context(**ctx)
    page = context.new_page()
    external: list[str] = []
    errors: list[str] = []

    def guard(route: Any) -> None:
        url = route.request.url
        if url.startswith("file:"):
            route.continue_()
        else:
            external.append(url)
            route.abort()

    page.route("**/*", guard)
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(path.as_uri())
    return page, external, errors


def test_renders_offline_without_errors(browser: Any, report: Path) -> None:
    page, external, errors = _open(browser, report)
    assert external == [] and errors == []
    assert page.locator("details.wi").count() == 5
    assert page.locator("#count").inner_text() == "5"
    assert "Resumo executivo" in page.locator("#summary").inner_text()


def test_search_is_accent_insensitive_and_shows_ancestors(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report)
    page.fill("#q", "verificacao de disponibilidade")  # task title has "verificação"
    assert page.locator("#count").inner_text() == "1"
    task = page.locator("details.wi.t-task")
    assert task.is_visible()  # ancestors kept visible and opened
    assert page.locator("details.wi.t-epic").is_visible()
    page.fill("#q", "não-existe-xyz")
    assert page.locator("#noresults").is_visible() and page.locator("#count").inner_text() == "0"


def test_type_filter_and_expand_collapse(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report)
    page.select_option("#ftype", "story")
    assert page.locator("#count").inner_text() == "2"
    page.select_option("#ftype", "")
    page.click("#expand")
    assert page.locator("details.wi[open]").count() == 5
    page.click("#collapse")
    assert page.locator("details.wi[open]").count() == 0


def test_criteria_and_story_render_natively(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report)
    page.click("#expand")
    story = page.locator("details.wi.t-story", has_text="Reservar um canteiro livre").first
    text = story.inner_text()
    assert "Eu como" in text and "Dado" in text and "CA-01" in text
    assert story.locator("strong", has_text="Eu como").count() >= 1


def test_mobile_layout_has_no_horizontal_overflow(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, viewport={"width": 375, "height": 740})
    for expand in (False, True):  # regression: long digests once widened the page by 173px
        if expand:
            page.click("#expand")
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 1


def test_keyboard_navigation_and_theme(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report)
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "skip"
    page.focus("#q")
    page.keyboard.type("Minhas")
    assert page.locator("#count").inner_text() == "1"
    before = page.evaluate("document.documentElement.getAttribute('data-theme')")
    page.click("#theme")
    after = page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert after in ("dark", "light") and after != before


def test_hostile_content_never_executes(browser: Any, tmp_path: Path) -> None:
    path = _report(tmp_path, hostile=True)
    page, external, _ = _open(browser, path)
    page.click("#expand")
    assert page.evaluate("window.__xss") is None
    assert page.locator("details.wi script").count() == 0
    assert page.locator("a[href^='javascript']").count() == 0
    assert "Épico" in page.locator("details.wi.t-epic > summary").inner_text()
    assert external == []


def test_embedded_canonical_json_matches_backlog(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report)
    page.click("#data summary")
    embedded = json.loads(page.locator("pre.json").inner_text())
    on_disk = json.loads((report.parent / "backlog.json").read_text(encoding="utf-8"))
    assert embedded == on_disk
