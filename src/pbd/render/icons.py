"""Typed work-item icon registry for the report's presentation appearances.

Appearance is presentation only: it never changes the canonical hierarchy, the destination profile,
type names or any field. Every pictogram below is an original, minimal 16x16 drawing made for PBD
(no vendor asset is copied, downloaded or referenced); the Azure DevOps and Jira appearances only
follow the publicly documented *conventions* of those tools (e.g. Epic crown/orange, User Story
book/blue, Task checklist/yellow in Azure Boards; Epic bolt/purple, Story bookmark/green, Task
check/blue in Jira). Projects can customize their own icons and colors; these are defaults, and PBD
is not affiliated with or certified by either vendor. See docs/reporting.md#appearance.

Icons are decorative (``aria-hidden``); the type is always also given as text or an accessible name.
Unknown or custom types fall back to a neutral glyph. No user-supplied SVG is ever rendered.
"""

# ruff: noqa: E501  (SVG path data)
from __future__ import annotations

APPEARANCES = ("generic", "azure", "jira")
TYPES = ("epic", "feature", "story", "enabler", "spike", "bug", "task")

# Glyphs (16x16). "tile" draws a rounded square in the type color with a light glyph; "mark" draws
# the glyph itself in the type color. Only static path/shape markup, no scripts, links or styles.
_TILE = '<rect x="1" y="1" width="14" height="14" rx="3" class="ti-b"/>'
GLYPHS: dict[str, dict[str, str]] = {
    "generic": {
        "epic": _TILE + '<path class="ti-g" d="M4.5 5.5h7M4.5 8h7M4.5 10.5h7"/>',
        "feature": _TILE + '<path class="ti-g" d="M5 5h6v6H5z"/>',
        "story": _TILE + '<path class="ti-g" d="M5 4.5h6v7.5l-3-2-3 2z"/>',
        "enabler": _TILE + '<path class="ti-g" d="M8 4l3.5 2v4L8 12l-3.5-2V6z"/>',
        "spike": _TILE
        + '<circle class="ti-g" cx="7.5" cy="7.5" r="2.5"/><path class="ti-g" d="M9.5 9.5l2 2"/>',
        "bug": _TILE + '<circle class="ti-gf" cx="8" cy="8" r="3"/>',
        "task": _TILE + '<path class="ti-g" d="M4.8 8.3l2.2 2.2 4.2-4.6"/>',
        "unknown": _TILE + '<circle class="ti-gf" cx="8" cy="8" r="1.6"/>',
    },
    "azure": {
        # crown
        "epic": '<path class="ti-f" d="M2 12.5h12L15 5l-3.6 2.8L8 2.5 4.6 7.8 1 5z"/><path class="ti-f" d="M2 13.5h12v1.5H2z"/>',
        # trophy
        "feature": '<path class="ti-f" d="M4 2h8v3.5a4 4 0 01-8 0z"/><path class="ti-s" d="M4 3.5H2v1a2 2 0 002 2M12 3.5h2v1a2 2 0 01-2 2"/>'
        '<path class="ti-f" d="M7 9.3h2V12h2.5v2h-7v-2H7z"/>',
        # open book
        "story": '<path class="ti-f" d="M1.5 3.5C3.5 2.5 6 2.6 7.5 4v9.5C6 12.2 3.5 12.1 1.5 13z"/>'
        '<path class="ti-f" d="M14.5 3.5C12.5 2.5 10 2.6 8.5 4v9.5c1.5-1.3 4-1.4 6-.5z"/>',
        # wrench-like hexagon bolt
        "enabler": '<path class="ti-f" d="M8 1.5l5.6 3.2v6.6L8 14.5l-5.6-3.2V4.7z"/><circle class="ti-h" cx="8" cy="8" r="2"/>',
        # flask
        "spike": '<path class="ti-f" d="M6 1.5h4v1.2H9.3v3.6l4 6.6c.5.9-.1 1.6-1 1.6H3.7c-.9 0-1.5-.7-1-1.6l4-6.6V2.7H6z"/>',
        # beetle
        "bug": '<ellipse class="ti-f" cx="8" cy="9.2" rx="3.6" ry="4.6"/><circle class="ti-f" cx="8" cy="3.6" r="2"/>'
        '<path class="ti-s" d="M4.4 7H2M4.2 10H1.8M4.6 12.8l-2 1.4M11.6 7H14M11.8 10h2.4M11.4 12.8l2 1.4"/>',
        # clipboard with checklist
        "task": '<path class="ti-f" d="M3 2.5h10v12H3z"/><path class="ti-h2" d="M5 6.2l1 1 1.7-1.9M9 6.6h2.4M5 10.2l1 1 1.7-1.9M9 10.6h2.4"/>',
        "unknown": '<rect class="ti-f" x="2.5" y="2.5" width="11" height="11" rx="2"/>',
    },
    "jira": {
        # lightning bolt
        "epic": _TILE + '<path class="ti-gf" d="M9 3L4.8 9h2.6l-.6 4L11.2 7H8.6z"/>',
        # feature has no Jira default type: neutral stacked layers, shown as the PBD canonical level
        "feature": _TILE + '<path class="ti-g" d="M8 4l4 2-4 2-4-2zM4 9l4 2 4-2"/>',
        # bookmark
        "story": _TILE + '<path class="ti-gf" d="M5.5 4h5v8.2L8 10.4l-2.5 1.8z"/>',
        "enabler": _TILE + '<path class="ti-g" d="M8 4l3.5 2v4L8 12l-3.5-2V6z"/>',
        "spike": _TILE
        + '<circle class="ti-g" cx="7.4" cy="7.4" r="2.6"/><path class="ti-g" d="M9.4 9.4l2.2 2.2"/>',
        # filled dot
        "bug": _TILE + '<circle class="ti-gf" cx="8" cy="8" r="3.2"/>',
        # check
        "task": _TILE + '<path class="ti-g" d="M4.6 8.2l2.3 2.3 4.5-4.8"/>',
        "unknown": _TILE + '<circle class="ti-gf" cx="8" cy="8" r="1.6"/>',
    },
}


def appearance_for_profile(profile_id: str | None) -> str:
    """Default appearance follows the known destination; otherwise generic. Presentation only."""
    pid = (profile_id or "").lower()
    if pid.startswith("azure"):
        return "azure"
    if pid.startswith("jira"):
        return "jira"
    return "generic"


def icon_key(itype: str) -> str:
    return itype if itype in TYPES else "unknown"


def sprite() -> str:
    """Hidden SVG sprite with one symbol per appearance and type (``#t-<appearance>-<type>``)."""
    symbols = "".join(
        f'<symbol id="t-{ap}-{ty}" viewBox="0 0 16 16">{glyph}</symbol>'
        for ap in APPEARANCES
        for ty, glyph in sorted(GLYPHS[ap].items())
    )
    return f'<svg width="0" height="0" class="sr-only" aria-hidden="true" focusable="false">{symbols}</svg>'


def type_icon(itype: str, appearance: str) -> str:
    key = icon_key(itype)
    return f'<svg class="ti ty-{key}" aria-hidden="true"><use href="#t-{appearance}-{key}"/></svg>'
