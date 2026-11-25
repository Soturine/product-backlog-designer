"""Native rich text for work-item fields, built from structured parts written by the agent.

Safety: all text is HTML-escaped first; the only inline markup recognized afterwards is
``**bold**`` and ``[label](url)`` with http, https or mailto URLs. No other HTML can be produced
from source-derived text.
"""

from __future__ import annotations

import html
import re
from typing import Any

LABELS: dict[str, dict[str, str]] = {
    "pt-BR": {
        "as": "Eu como",
        "want": "gostaria que",
        "so": "para",
        "when": "Quando",
        "job_want": "quero",
        "so_that": "para que",
        "objective": "Objetivo",
        "context": "Contexto",
        "in_scope": "No escopo",
        "out_scope": "Fora do escopo",
        "outcome": "Resultado esperado",
        "capability": "Capacidade",
        "value": "Valor",
        "rules": "Regras relacionadas",
        "tech_capability": "Capacidade técnica",
        "question": "Pergunta a responder",
        "timebox": "Timebox",
        "decision": "Decisão esperada",
        "summary": "Objetivo",
        "activities": "Atividades",
        "verification": "Verificação",
        "notes": "Observações",
        "observed": "Comportamento observado",
        "expected": "Comportamento esperado",
        "steps": "Passos para reproduzir",
        "ac_id": "ID",
        "ac_criterion": "Critério de aceite",
        "ac_result": "Resultado esperado",
        "given": "Dado",
        "gwhen": "Quando",
        "then": "Então",
        "and": "E",
        "acceptance": "Critérios de aceite",
    },
    "en": {
        "as": "As a",
        "want": "I want",
        "so": "so that",
        "when": "When",
        "job_want": "I want to",
        "so_that": "so that",
        "objective": "Objective",
        "context": "Context",
        "in_scope": "In scope",
        "out_scope": "Out of scope",
        "outcome": "Expected outcome",
        "capability": "Capability",
        "value": "Value",
        "rules": "Related rules",
        "tech_capability": "Technical capability",
        "question": "Question to answer",
        "timebox": "Timebox",
        "decision": "Expected decision",
        "summary": "Objective",
        "activities": "Activities",
        "verification": "Verification",
        "notes": "Notes",
        "observed": "Observed behavior",
        "expected": "Expected behavior",
        "steps": "Steps to reproduce",
        "ac_id": "ID",
        "ac_criterion": "Acceptance criterion",
        "ac_result": "Expected result",
        "given": "Given",
        "gwhen": "When",
        "then": "Then",
        "and": "And",
        "acceptance": "Acceptance criteria",
    },
    "es": {
        "as": "Como",
        "want": "quiero",
        "so": "para",
        "when": "Cuando",
        "job_want": "quiero",
        "so_that": "para que",
        "objective": "Objetivo",
        "context": "Contexto",
        "in_scope": "Dentro del alcance",
        "out_scope": "Fuera del alcance",
        "outcome": "Resultado esperado",
        "capability": "Capacidad",
        "value": "Valor",
        "rules": "Reglas relacionadas",
        "tech_capability": "Capacidad técnica",
        "question": "Pregunta a responder",
        "timebox": "Timebox",
        "decision": "Decisión esperada",
        "summary": "Objetivo",
        "activities": "Actividades",
        "verification": "Verificación",
        "notes": "Notas",
        "observed": "Comportamiento observado",
        "expected": "Comportamiento esperado",
        "steps": "Pasos para reproducir",
        "ac_id": "ID",
        "ac_criterion": "Criterio de aceptación",
        "ac_result": "Resultado esperado",
        "given": "Dado",
        "gwhen": "Cuando",
        "then": "Entonces",
        "and": "Y",
        "acceptance": "Criterios de aceptación",
    },
}

# kind -> (required parts, ordered optional parts)
CONTENT_KINDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "epic": (("objective",), ("context", "in_scope", "out_scope", "outcome", "notes")),
    "feature": (("capability",), ("value", "outcome", "rules", "notes")),
    "role_goal_benefit": (("actor", "want", "benefit"), ("context", "notes")),
    "job_story": (("situation", "motivation", "outcome"), ("context", "notes")),
    "enabler": (("capability", "outcome"), ("context", "notes")),
    "spike": (("question", "decision"), ("timebox", "context", "notes")),
    "task": (("summary",), ("activities", "outcome", "verification", "notes")),
    "bug": (("observed", "expected"), ("steps", "context", "notes")),
}
LIST_PARTS = {"in_scope", "out_scope", "rules", "activities", "steps", "notes"}
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]\n]+)\]\(((?:https?://|mailto:)[^\s)\"'<>]+)\)")


class RichTextError(ValueError):
    pass


def labels(language: str) -> dict[str, str]:
    if language in LABELS:
        return LABELS[language]
    base = language.split("-")[0]
    for key in LABELS:
        if key.split("-")[0] == base:
            return LABELS[key]
    return LABELS["en"]


def inline(text: str) -> str:
    """Escape ``text`` and convert the tiny allowed inline markup."""
    out = html.escape(text, quote=True)
    out = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', out)
    return _BOLD.sub(r"<strong>\1</strong>", out)


def validate_content(content: Any) -> list[str]:
    if not isinstance(content, dict):
        return ["content must be an object"]
    kind = content.get("kind")
    if kind not in CONTENT_KINDS:
        return [f"content.kind must be one of {sorted(CONTENT_KINDS)}"]
    required, optional = CONTENT_KINDS[kind]
    errors = []
    for part in required:
        value = content.get(part)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"content.{part} is required for {kind}")
    for key, value in content.items():
        if key == "kind":
            continue
        if key not in required and key not in optional:
            errors.append(f"content.{key} is not a part of {kind}")
        elif key in LIST_PARTS:
            is_list = isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)
            if not is_list and not (isinstance(value, str) and value.strip()):
                errors.append(f"content.{key} must be text or a list of non-empty text")
        elif not (isinstance(value, str) and value.strip()):
            errors.append(f"content.{key} must be non-empty text")
    return errors


def _items(value: Any) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def _section(label: str, value: Any) -> str:
    if isinstance(value, list):
        lis = "".join(f"<li>{inline(v)}</li>" for v in value)
        return f"<p><strong>{html.escape(label)}</strong></p><ul>{lis}</ul>"
    return f"<p><strong>{html.escape(label)}</strong>: {inline(value)}</p>"


def _strip_label(text: str, label: str) -> str:
    """Drop a leading prefix the agent already wrote (regression: 'Quando Quando', 'quero quero')."""
    stripped = text.strip().rstrip(".").rstrip(",")
    words = label.split()
    # Any prefix or suffix of the label repeated by the agent ("gostaria que", "que", "Quando") is dropped.
    candidates = sorted(
        {" ".join(words[:n]) for n in range(1, len(words) + 1)}
        | {" ".join(words[n:]) for n in range(1, len(words))},
        key=len,
        reverse=True,
    )
    for candidate in candidates:
        if stripped.casefold().startswith(candidate.casefold() + " "):
            return stripped[len(candidate) + 1 :].lstrip(" ,")
    return stripped


def description_html(content: dict[str, Any], language: str) -> str:
    errors = validate_content(content)
    if errors:
        raise RichTextError("; ".join(errors))
    lab = labels(language)
    kind = content["kind"]
    c = content
    parts: list[str] = []
    if kind == "role_goal_benefit":
        parts.append(
            f"<p><strong>{html.escape(lab['as'])}</strong> {inline(_strip_label(c['actor'], lab['as']))}, "
            f"<strong>{html.escape(lab['want'])}</strong> {inline(_strip_label(c['want'], lab['want']))}, "
            f"<strong>{html.escape(lab['so'])}</strong> {inline(_strip_label(c['benefit'], lab['so']))}.</p>"
        )
        rest: tuple[str, ...] = ("context", "notes")
    elif kind == "job_story":
        situation = inline(_strip_label(c["situation"], lab["when"]))
        motivation = inline(_strip_label(c["motivation"], lab["job_want"]))
        outcome = inline(_strip_label(c["outcome"], lab["so_that"]))
        parts.append(
            f"<p><strong>{html.escape(lab['when'])}</strong> {situation}, "
            f"<strong>{html.escape(lab['job_want'])}</strong> {motivation}, "
            f"<strong>{html.escape(lab['so_that'])}</strong> {outcome}.</p>"
        )
        rest = ("context", "notes")
    else:
        mapping = {
            "epic": [
                ("objective", "objective"),
                ("context", "context"),
                ("in_scope", "in_scope"),
                ("out_scope", "out_scope"),
                ("outcome", "outcome"),
            ],
            "feature": [
                ("capability", "capability"),
                ("value", "value"),
                ("outcome", "outcome"),
                ("rules", "rules"),
            ],
            "enabler": [("capability", "tech_capability"), ("outcome", "outcome"), ("context", "context")],
            "spike": [
                ("question", "question"),
                ("timebox", "timebox"),
                ("decision", "decision"),
                ("context", "context"),
            ],
            "task": [
                ("summary", "summary"),
                ("activities", "activities"),
                ("outcome", "outcome"),
                ("verification", "verification"),
            ],
            "bug": [
                ("observed", "observed"),
                ("expected", "expected"),
                ("steps", "steps"),
                ("context", "context"),
            ],
        }[kind]
        for part, label_key in mapping:
            if part in c:
                value = _items(c[part]) if part in LIST_PARTS else c[part]
                parts.append(_section(lab[label_key], value))
        rest = ("notes",)
    for part in rest:
        if part in c:
            parts.append(
                _section(
                    lab["notes" if part == "notes" else part],
                    _items(c[part]) if part in LIST_PARTS else c[part],
                )
            )
    return "".join(parts)


def criterion_sentence(crit: dict[str, Any]) -> str:
    """Plain one-line rendering used by list style and plain-text exports."""
    outcomes = [str(o) for o in crit.get("expected_outcomes", [])]
    if crit.get("text"):
        text = str(crit["text"])
        # Never drop an expected outcome: append those the statement does not already contain.
        missing = [o for o in outcomes if o.casefold() not in text.casefold()]
        return f"{text} → {'; '.join(missing)}" if missing else text
    lead = ", ".join(p for p in (crit.get("condition"), crit.get("trigger")) if p)
    outcome = "; ".join(crit.get("expected_outcomes", []))
    return f"{lead}: {outcome}" if lead else outcome


def criteria_html(criteria: list[dict[str, Any]], style: str, language: str) -> str:
    """Render criteria of one work item in the chosen native style (list, table or gherkin)."""
    lab = labels(language)
    if not criteria:
        return ""
    if style == "table":
        head = (
            f"<tr><th>{html.escape(lab['ac_id'])}</th><th>{html.escape(lab['ac_criterion'])}</th>"
            f"<th>{html.escape(lab['ac_result'])}</th></tr>"
        )
        rows = []
        for c in criteria:
            cond = c.get("text") or ", ".join(p for p in (c.get("condition"), c.get("trigger")) if p)
            outcomes = "<br>".join(inline(o) for o in c["expected_outcomes"])
            rows.append(
                f"<tr><td>{html.escape(c['visible_id'])}</td><td>{inline(cond)}</td><td>{outcomes}</td></tr>"
            )
        return f"<table><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table>"
    if style == "gherkin":
        blocks = []
        for c in criteria:
            lines = [f"<strong>{html.escape(c['visible_id'])}</strong>"]
            if c.get("condition"):
                lines.append(f"<strong>{html.escape(lab['given'])}</strong> {inline(c['condition'])}")
            if c.get("trigger"):
                lines.append(f"<strong>{html.escape(lab['gwhen'])}</strong> {inline(c['trigger'])}")
            for i, outcome in enumerate(c["expected_outcomes"]):
                word = lab["then"] if i == 0 else lab["and"]
                lines.append(f"<strong>{html.escape(word)}</strong> {inline(outcome)}")
            blocks.append("<p>" + "<br>".join(lines) + "</p>")
        return "".join(blocks)
    lis = "".join(
        f"<li><strong>{html.escape(c['visible_id'])}</strong> {inline(criterion_sentence(c))}</li>"
        for c in criteria
    )
    return f"<ul>{lis}</ul>"


def strip_html(value: str) -> str:
    """Plain text for CSV/Markdown cells (block boundaries become newlines)."""
    text = re.sub(r"<br\s*/?>|</p>|</li>|</tr>", "\n", value)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())
