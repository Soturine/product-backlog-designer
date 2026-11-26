"""Automated accessibility scan with axe-core (WCAG 2.0/2.1/2.2 A and AA rules) on every view.

axe-core is local test tooling only (never shipped, never loaded by a report): set ``PBD_AXE_JS`` to
a pinned ``axe.min.js`` (the corrective round used axe-core 4.10.2 installed with npm outside the
repository). Without it the test is skipped, not passed. The scan cannot certify WCAG conformance:
manual checks (keyboard, screen reader, reflow) remain separate evidence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from pbd.pipeline.finalize import finalize
from pbd.pipeline.review import submit_review
from tests.e2e.test_report_browser import browser  # noqa: F401  (fixture re-export)
from tests.pipeline.library_fixture import designed_run, review_payload

pytestmark = pytest.mark.playwright
AXE = os.environ.get("PBD_AXE_JS")
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


@pytest.mark.skipif(not AXE or not Path(AXE).is_file(), reason="PBD_AXE_JS (pinned axe.min.js) not provided")
@pytest.mark.parametrize(
    ("theme", "width", "motion"),
    [("light", 1280, "reduce"), ("dark", 390, "reduce"), ("light", 1280, "no-preference")],
)
def test_no_axe_violations_on_any_view(
    browser: Any,  # noqa: F811
    tmp_path: Path,
    theme: str,
    width: int,
    motion: str,
) -> None:
    run = designed_run(tmp_path, formats=["azure"], profile="azure-agile", title="Biblioteca")
    submit_review(run, review_payload(run))
    finalize(run)
    report = run.path("output/report.html")
    axe = Path(str(AXE)).read_text(encoding="utf-8")
    ctx = browser.new_context(
        viewport={"width": width, "height": 900}, bypass_csp=True, color_scheme=theme, reduced_motion=motion
    )
    page = ctx.new_page()
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
    page.goto(report.as_uri())
    violations = []
    for view in page.eval_on_selector_all(".view", "els => els.map(e => e.id)"):
        page.goto(report.as_uri() + "#" + view)
        if view == "backlog":
            page.locator("#tree a.lbl").first.click()
        # under normal motion, scan the settled view (a fade-in is transient, not the resting state)
        page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")
        page.add_script_tag(content=axe)
        res = page.evaluate(
            "async (tags) => await axe.run(document, {runOnly: {type: 'tag', values: tags}, "
            "resultTypes: ['violations']})",
            TAGS,
        )
        violations += [(view, v["id"], [n["target"] for n in v["nodes"][:3]]) for v in res["violations"]]
    ctx.close()
    assert violations == []
