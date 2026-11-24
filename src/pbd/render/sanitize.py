"""Allowlist HTML sanitizer for rich-text fields shown in reports (defense in depth).

PBD generates rich text itself from escaped parts, but a canonical file on disk may have been
edited; the report therefore never trusts stored HTML.
"""

from __future__ import annotations

import html
from html.parser import HTMLParser

ALLOWED = {
    "p",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "br",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "a",
    "code",
    "pre",
    "blockquote",
    "h3",
    "h4",
    "span",
}
VOID = {"br"}
SAFE_SCHEMES = ("http://", "https://", "mailto:")


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "iframe", "object", "embed", "template", "svg", "math"):
            self.skip += 1
            return
        if self.skip or tag not in ALLOWED:
            return
        attr = ""
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if href.strip().lower().startswith(SAFE_SCHEMES):
                attr = f' href="{html.escape(href.strip(), quote=True)}" rel="noopener noreferrer"'
        self.out.append(f"<{tag}{attr}>")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "iframe", "object", "embed", "template", "svg", "math"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in ALLOWED or tag in VOID or tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def close(self) -> None:
        super().close()
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")


def sanitize_html(value: str) -> str:
    parser = _Sanitizer()
    parser.feed(value)
    parser.close()
    return "".join(parser.out)
