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
            '<p>ok</p><script>window.__xss=3</script><a href="javascript:alert(1)">x</a></pre></script>'
        )
        run.write_artifact("stages/backlog.draft.json", draft)
        run.save()
    submit_review(run, review_payload(run))
    finalize(run)
    return run.path("output/report.html")


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _report(tmp_path_factory.mktemp("rep"))


def _open(browser: Any, path: Path, hash_: str = "", **ctx: Any) -> tuple[Any, list[str], list[str]]:
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
    page.goto(path.as_uri() + hash_)
    return page, external, errors


def test_renders_offline_without_errors_and_opens_on_overview(browser: Any, report: Path) -> None:
    page, external, errors = _open(browser, report)
    assert external == [] and errors == []
    assert page.locator("#overview").is_visible() and not page.locator("#backlog").is_visible()
    assert "Visão geral" in page.locator("#crumb-view").inner_text()
    assert page.locator("#tree li[data-id]").count() == 5


def test_navigation_deep_links_and_history(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report)
    page.click(".side a[data-view=backlog]")
    assert page.locator("#backlog").is_visible()
    assert page.locator(".side a[data-view=backlog]").get_attribute("aria-current") == "page"
    page.click("#tree a.lbl >> text=Consultar minhas reservas")
    assert "#item-" in page.url
    art = page.locator("article.item.is-active")
    assert art.count() == 1 and "Consultar minhas reservas" in art.inner_text()
    page.go_back()
    page.wait_for_timeout(100)
    assert page.locator("#backlog").is_visible()
    crit = page.locator("ol.criteria > li").first.get_attribute("id")
    page.goto(report.as_uri() + "#" + crit)
    page.wait_for_timeout(100)
    assert page.locator(f"#{crit}").is_visible()


def test_search_is_accent_insensitive_keeps_context_and_highlights(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, "#backlog")
    page.fill("#q", "verificacao de disponibilidade")  # task title has "verificação"
    assert page.locator("#ex-count").inner_text().startswith("1 ")
    assert page.locator("#tree li[data-type=task]").is_visible()
    epic = page.locator("#tree li[data-type=epic] > .row")
    assert epic.is_visible() and "ctx" in (epic.get_attribute("class") or "")  # ancestor shown, not counted
    assert page.locator("#tree mark").count() == 1
    page.fill("#q", "não-existe-xyz")
    assert page.locator("#ex-none").is_visible() and page.locator("#ex-count").inner_text().startswith(
        "Nenhum"
    )


def test_filters_chips_and_clear(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, "#backlog")
    page.select_option("#f-type", "story")
    assert page.locator("#ex-count").inner_text().startswith("2 ")
    assert page.locator("#chips .chip").count() == 1
    page.click("#chips .chip")
    assert page.locator("#chips .chip").count() == 0 and page.locator("#ex-count").inner_text().startswith(
        "5 "
    )
    page.select_option("#f-type", "task")
    page.click("#ex-clear")
    assert page.locator("#ex-count").inner_text().startswith("5 ")


def test_tree_toggle_levels_and_table_view(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, "#backlog")
    page.click("#ex-collapse")
    assert not page.locator("#tree li[data-type=feature]").is_visible()
    page.click("#ex-expand")
    assert page.locator("#tree li[data-type=task]").is_visible()
    page.click("[data-xview=table]")
    assert page.locator("#itable").is_visible() and page.locator("#itable tbody tr").count() == 5


def test_criteria_render_natively_with_stable_ids(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, "#backlog")
    page.click("#tree a.lbl >> text=Reservar um canteiro livre")
    art = page.locator("article.item.is-active")
    text = art.inner_text()
    assert "Eu como" in text and "Dado" in text and "CA-01" in text
    assert art.locator("strong", has_text="Eu como").count() >= 1


def test_language_switch_is_offline_and_keeps_content(browser: Any, report: Path) -> None:
    page, external, _ = _open(browser, report)
    page.select_option("#lang-sel", "en")
    assert page.evaluate("document.documentElement.lang") == "en"
    assert "Overview" in page.locator("#crumb-view").inner_text()
    assert page.locator("a.skip").inner_text() == "Skip to content"
    page.select_option("#lang-sel", "es")
    assert page.locator("a.skip").inner_text() == "Ir al contenido"
    assert "Reservar um canteiro livre" in page.content()  # backlog content is not translated
    assert external == []


def test_theme_copy_and_download(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, "#backlog", permissions=["clipboard-read", "clipboard-write"])
    page.select_option("#theme-sel", "dark")
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    page.click("#tree a.lbl >> nth=0")
    copy = page.locator("article.item.is-active .copy").first
    copy.click()
    page.wait_for_function("document.getElementById('toast').textContent.length > 0")
    assert page.evaluate("navigator.clipboard.readText()").startswith("PBD-")
    page.goto(report.as_uri() + "#data")
    with page.expect_download() as dl:
        page.click("[data-download=canonical]")
    assert dl.value.suggested_filename == "backlog.json"


def test_mobile_list_detail_back_and_drawer(browser: Any, report: Path) -> None:
    for width in (390, 320):
        page, _, _ = _open(browser, report, "#backlog", viewport={"width": width, "height": 740})
        assert (
            page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1
        )
        page.select_option("#f-type", "story")
        page.click("#tree a.lbl >> text=Reservar um canteiro livre")
        assert (
            page.locator("article.item.is-active").is_visible() and not page.locator(".master").is_visible()
        )
        assert (
            page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1
        )
        page.locator("article.item.is-active .back").click()
        assert page.locator(".master").is_visible() and page.locator("#f-type").input_value() == "story"
        page.click("#menu")
        assert page.locator("#side").is_visible()
        page.keyboard.press("Escape")
        page.wait_for_timeout(350)
        assert page.evaluate("document.body.classList.contains('nav-open')") is False


def test_keyboard_skip_link_and_tree_arrows(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report)
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "skip"
    page.click(".side a[data-view=backlog]")
    page.focus("#tree a.lbl >> nth=0")
    page.keyboard.press("ArrowDown")
    assert "Reservar canteiro por temporada" in page.evaluate("document.activeElement.textContent")


def test_works_without_javascript(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, java_script_enabled=False)
    for vid in ("overview", "backlog", "requirements", "findings", "quality", "sources", "data"):
        assert page.locator(f"#{vid}").is_visible()
    assert page.locator("article.item").count() == 5 and page.locator("article.item").first.is_visible()


def test_reduced_motion_disables_animation(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, "#backlog", reduced_motion="reduce")
    duration = page.evaluate("getComputedStyle(document.querySelector('.view.is-active')).animationName")
    assert duration == "none"


def test_hostile_content_never_executes(browser: Any, tmp_path: Path) -> None:
    path = _report(tmp_path, hostile=True)
    page, external, _ = _open(browser, path, "#backlog")
    page.click("#tree a.lbl >> nth=0")
    assert page.evaluate("window.__xss") is None
    assert page.locator("article.item script").count() == 0
    assert page.locator("a[href^='javascript']").count() == 0
    assert "Épico" in page.locator("article.item.is-active h3").inner_text()
    assert external == []


def test_embedded_canonical_json_matches_backlog(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report, "#data")
    embedded = json.loads(page.locator("pre#canonical").text_content())
    on_disk = json.loads((report.parent / "backlog.json").read_text(encoding="utf-8"))
    assert embedded == on_disk


def test_html_counts_match_canonical_data(browser: Any, report: Path) -> None:
    page, _, _ = _open(browser, report)
    backlog = json.loads((report.parent / "backlog.json").read_text(encoding="utf-8"))
    gates = json.loads((report.parent / "gates.json").read_text(encoding="utf-8"))
    assert page.locator("article.item").count() == len(backlog["items"])
    assert page.locator("ol.criteria > li").count() == len(backlog["criteria"])
    assert page.locator("details.gate").count() == len(gates["gates"])
    for g in gates["gates"]:
        assert page.locator(f"#gate-{g['id']}").get_attribute("data-status") == g["status"]
