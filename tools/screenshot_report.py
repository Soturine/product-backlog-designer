"""Capture documentation screenshots and a short demo video of generated reports.

Uses the system Edge/Chrome through Playwright (no browser download); every non-file request is
blocked, so the captures also prove the reports are offline.

Usage: python tools/screenshot_report.py [examples/reports] [docs/images/report]
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
SHOTS: list[tuple[str, str, int, int, str, str, str]] = [
    # name, example, width, height, hash, theme, locale
    ("overview-1440-light-pt", "generate", 1440, 1000, "", "light", "pt-BR"),
    ("overview-1440-dark-en", "generate", 1440, 1000, "", "dark", "en"),
    ("backlog-1280-light-pt", "generate", 1280, 900, "#backlog", "light", "pt-BR"),
    ("item-1280-dark-es", "generate", 1280, 900, "#item", "dark", "es"),
    ("requirements-1280-light-en", "generate", 1280, 900, "#requirements", "light", "en"),
    ("quality-1280-light-pt", "generate", 1280, 900, "#quality", "light", "pt-BR"),
    ("integration-1280-dark-pt", "generate", 1280, 900, "#integration", "dark", "pt-BR"),
    ("audit-overview-1440-light-pt", "audit", 1440, 1000, "", "light", "pt-BR"),
    ("audit-findings-1280-light-pt", "audit", 1280, 900, "#findings", "light", "pt-BR"),
    ("compare-overview-1440-light-pt", "compare", 1440, 1000, "", "light", "pt-BR"),
    ("compare-alignment-1280-dark-en", "compare", 1280, 900, "#alignment", "dark", "en"),
    ("overview-768-light-pt", "generate", 768, 1024, "", "light", "pt-BR"),
    ("backlog-390-light-pt", "generate", 390, 844, "#backlog", "light", "pt-BR"),
    ("item-390-dark-en", "generate", 390, 844, "#item", "dark", "en"),
    ("overview-320-light-es", "generate", 320, 640, "", "light", "es"),
    # corrective round: readiness, gate explanations, appearance, table and team plan
    ("readiness-overview-1440-light-pt", "readiness", 1440, 1000, "", "light", "pt-BR"),
    ("readiness-blocked-item-1280-light-pt", "readiness", 1280, 900, "#blocked", "light", "pt-BR"),
    ("readiness-tree-azure-1280-light-pt", "readiness", 1280, 900, "#backlog@azure", "light", "pt-BR"),
    ("readiness-tree-jira-1280-dark-pt", "readiness", 1280, 900, "#backlog@jira", "dark", "pt-BR"),
    ("readiness-table-1280-light-en", "readiness", 1280, 900, "#table", "light", "en"),
    ("gate-explained-1280-light-pt", "readiness", 1280, 900, "#gate-G02", "light", "pt-BR"),
    ("readiness-blocked-item-390-light-pt", "readiness", 390, 844, "#blocked", "light", "pt-BR"),
    ("plan-team-1280-light-pt", "plan", 1280, 2200, "", "light", "pt-BR"),
]


def _launch(pw: Any) -> Any:
    for channel in ("msedge", "chrome"):
        try:
            return pw.chromium.launch(channel=channel)
        except Exception:  # noqa: S112 - try the next installed browser
            continue
    raise SystemExit("no system Edge/Chrome found")


def _guard(route: Any) -> None:
    if route.request.url.startswith("file:"):
        route.continue_()
    else:
        raise SystemExit(f"report attempted a network request: {route.request.url}")


def _prepare(page: Any, report: Path, hash_: str, theme: str, locale: str) -> None:
    page.route("**/*", _guard)
    hash_, _, appearance = hash_.partition("@")
    special = hash_ in ("#item", "#blocked", "#table")
    page.goto(report.resolve().as_uri() + ("" if special else hash_))
    page.select_option("#lang-sel", locale)
    page.evaluate(f"document.documentElement.setAttribute('data-theme', '{theme}')")
    if appearance:
        page.select_option("#appearance-sel", appearance)
    if hash_ == "#item":
        page.goto(report.resolve().as_uri() + "#backlog")
        page.locator("#tree li[data-type=story] a.lbl").first.click()
    if hash_ == "#blocked":
        page.goto(report.resolve().as_uri() + "#backlog")
        page.locator("#tree li[data-readiness=blocked] a.lbl").first.click()
    if hash_ == "#table":
        page.goto(report.resolve().as_uri() + "#backlog")
        page.click(".seg [data-xview=table]")
    page.wait_for_timeout(450)
    page.evaluate("document.getElementById('toast').hidden = true")


def _demo_frames(browser: Any, report: Path) -> list[bytes]:
    """Screens of a short local flow: overview, explorer search, item detail, gates, EN, dark."""
    page = browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
    page.route("**/*", _guard)
    page.goto(report.resolve().as_uri())
    page.wait_for_timeout(400)
    frames = [page.screenshot()]
    steps = [
        lambda: page.click(".side a[data-view=backlog]"),
        lambda: page.select_option("#f-readiness", "blocked"),
        lambda: page.locator("#tree li[data-readiness=blocked] a.lbl").first.click(),
        lambda: page.select_option("#appearance-sel", "azure"),
        lambda: page.select_option("#appearance-sel", "jira"),
        lambda: page.goto(report.resolve().as_uri() + "#gate-G08"),
        lambda: (
            page.select_option("#lang-sel", "en"),
            page.evaluate("document.getElementById('toast').hidden = true"),
        ),
        lambda: page.select_option("#theme-sel", "dark"),
    ]
    for step in steps:
        step()
        page.wait_for_timeout(450)
        frames.append(page.screenshot())
    page.close()
    return frames


def _chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    pos, out = 8, []
    while pos < len(png):
        length = struct.unpack(">I", png[pos : pos + 4])[0]
        ctype = png[pos + 4 : pos + 8]
        out.append((ctype, png[pos + 8 : pos + 8 + length]))
        pos += 12 + length
    return out


def _chunk(ctype: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    )


def apng(frames: list[bytes], delay_ms: int) -> bytes:
    """Assemble same-size PNG frames into an animated PNG (APNG) without any imaging library."""
    first = _chunks(frames[0])
    ihdr = next(d for t, d in first if t == b"IHDR")
    width, height = struct.unpack(">II", ihdr[:8])
    out = [PNG_SIGNATURE, _chunk(b"IHDR", ihdr), _chunk(b"acTL", struct.pack(">II", len(frames), 0))]
    seq = 0
    for n, frame in enumerate(frames):
        chunks = _chunks(frame)
        if next(d for t, d in chunks if t == b"IHDR") != ihdr:
            raise ValueError("all frames must share size and colour type")
        fctl = struct.pack(">IIIIIHHBB", seq, width, height, 0, 0, delay_ms, 1000, 0, 0)
        out.append(_chunk(b"fcTL", fctl))
        seq += 1
        for ctype, data in chunks:
            if ctype != b"IDAT":
                continue
            if n == 0:
                out.append(_chunk(b"IDAT", data))
            else:
                out.append(_chunk(b"fdAT", struct.pack(">I", seq) + data))
                seq += 1
    out.append(_chunk(b"IEND", b""))
    return b"".join(out)


def main(examples: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = _launch(pw)
        for name, example, w, h, hash_, theme, locale in SHOTS:
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            name_html = "plan-report.html" if example == "plan" else "report.html"
            _prepare(page, examples / example / name_html, hash_, theme, locale)
            page.screenshot(path=str(out / f"{name}.png"))
            page.close()
        frames = _demo_frames(browser, examples / "readiness" / "report.html")
        (out / "report-demo.png").write_bytes(apng(frames, delay_ms=1300))
        browser.close()
    print(f"{len(SHOTS)} screenshots and the report-demo.png animation written to {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(
        Path(args[0]) if args else ROOT / "examples" / "reports",
        Path(args[1]) if len(args) > 1 else ROOT / "docs" / "images" / "report",
    )
