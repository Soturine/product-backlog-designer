"""Capture screenshots of a generated report.html for documentation (system Edge/Chrome via Playwright).

Usage: python tools/screenshot_report.py <report.html> <out-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main(report: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = None
        for channel in ("msedge", "chrome"):
            try:
                browser = pw.chromium.launch(channel=channel)
                break
            except Exception:  # noqa: S112 - try the next installed browser
                continue
        if browser is None:
            raise SystemExit("no system Edge/Chrome found")
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        page.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
        page.goto(report.resolve().as_uri())
        page.screenshot(path=str(out / "report-summary.png"))
        page.click("#expand")
        page.locator("#backlog").scroll_into_view_if_needed()
        story = page.locator("details.wi.t-story").first
        story.scroll_into_view_if_needed()
        page.screenshot(path=str(out / "report-backlog.png"))
        page.locator("#gates").scroll_into_view_if_needed()
        page.screenshot(path=str(out / "report-gates.png"))
        page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
        page.locator("#summary").scroll_into_view_if_needed()
        page.screenshot(path=str(out / "report-dark.png"))
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        mobile.goto(report.resolve().as_uri())
        mobile.screenshot(path=str(out / "report-mobile.png"))
        browser.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
