"""Interface catalogs for reports (pt-BR, en, es).

Three languages are kept apart:

- interface language: labels, navigation, enum names, explanations (this module);
- artifact language: the language the agents wrote the backlog in (``backlog.language``);
- source language: quotes are shown verbatim and never translated.

Catalogs live in ``locales/<locale>.json`` and must share exactly the same keys (a parity test
enforces it). Values are strings with ``{name}`` placeholders, or ``{"one": ..., "other": ...}``
plural forms (CLDR categories) with an optional explicit ``"zero"`` phrase ("Nenhuma pergunta").
Missing keys fall back to ``en``; a key missing from ``en`` raises, so a typo cannot silently
print a raw key. Canonical codes (G01, PASS, COVERED, System.Title) stay in the data and
are shown through ``enum.<group>.<code>`` labels.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

LOCALES = ("pt-BR", "en", "es")
FALLBACK = "en"


def resolve_locale(language: str | None) -> str:
    """Map a run language (``pt-BR``, ``pt``, ``en-US``, ``es-AR``...) to a catalog locale."""
    lang = (language or FALLBACK).strip().lower()
    if lang.startswith("pt"):
        return "pt-BR"
    if lang.startswith("es"):
        return "es"
    return "en"


@cache
def catalog(locale: str) -> dict[str, Any]:
    if locale not in LOCALES:
        raise KeyError(f"unknown locale {locale!r}")
    data = resources.files("pbd.render").joinpath("locales", f"{locale}.json").read_text(encoding="utf-8")
    loaded: dict[str, Any] = json.loads(data)
    return loaded


def plural_category(locale: str, n: int) -> str:
    """CLDR cardinal 'one'/'other' for the supported locales (pt-BR treats 0 and 1 as 'one')."""
    if locale == "pt-BR":
        return "one" if n in (0, 1) else "other"
    return "one" if n == 1 else "other"


def format_number(locale: str, n: int | float) -> str:
    text = f"{n:,.1f}" if isinstance(n, float) and not n.is_integer() else f"{int(n):,}"
    if locale in ("pt-BR", "es"):
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


class Translator:
    def __init__(self, locale: str) -> None:
        self.locale = locale
        self._cat = catalog(locale)
        self._fallback = catalog(FALLBACK)

    def raw(self, key: str) -> Any:
        if key in self._cat:
            return self._cat[key]
        if key in self._fallback:
            return self._fallback[key]
        raise KeyError(f"missing UI string {key!r}")

    def has(self, key: str) -> bool:
        return key in self._cat or key in self._fallback

    def __call__(self, key: str, n: int | None = None, **params: Any) -> str:
        value = self.raw(key)
        if isinstance(value, dict):
            count = n if n is not None else int(params.get("n", 0))
            value = (
                value["zero"]
                if count == 0 and "zero" in value
                else value[plural_category(self.locale, count)]
            )
            params.setdefault("n", format_number(self.locale, count))
        elif n is not None:
            params.setdefault("n", n)
        text = str(value)
        for name, param in params.items():
            shown = format_number(self.locale, param) if isinstance(param, int | float) else str(param)
            text = text.replace("{" + name + "}", shown)
        return text

    def enum(self, group: str, code: Any) -> str:
        """Human label for a canonical code; unknown codes are shown as-is (never guessed)."""
        key = f"enum.{group}.{code}"
        return self(key) if self.has(key) else str(code)
