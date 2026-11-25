"""Offline product report rendered deterministically from canonical artifacts.

One design system and one shell serve every mode (generation, audit, comparison; planning,
evolution and integration views plug into the same components). The page opens on an executive
overview and drills down into a master/detail backlog explorer, requirements and traceability,
findings and questions, quality gates with evidence, sources, the local integration package and
the canonical data.

- All content is rendered server-side and readable without JavaScript; the embedded script only
  adds routing, filters, selection, copy/download, theme and offline interface-language switching.
- No external resource of any kind. The Content-Security-Policy allows exactly the embedded
  stylesheet and script by SHA-256 hash; there are no inline handlers or style attributes.
- Interface text comes from ``locales/*.json`` (see ``i18n``); canonical codes stay in the data and
  backlog content keeps the language the agents wrote it in (marked with ``lang``).
- The renderer never draws a new semantic conclusion: sentences are filled from recorded counts.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
from collections import Counter
from functools import cache
from importlib import resources
from typing import Any

from pbd.render.exports import criteria_by_parent, tree_order
from pbd.render.i18n import LOCALES, Translator, catalog, resolve_locale
from pbd.render.richtext import criteria_html, criterion_sentence, inline, labels, strip_html
from pbd.render.sanitize import sanitize_html

TONES = {
    "gate_status": {
        "PASS": "pass",
        "FAIL": "fail",
        "BLOCKED": "warn",
        "NOT_RUN": "neutral",
        "NOT_APPLICABLE": "neutral",
    },
    "verdict": {"pass": "pass", "concern": "warn", "fail": "fail"},
    "support": {"supported": "pass", "proposal_justified": "info", "unsupported": "fail"},
    "disposition": {
        "COVERED": "pass",
        "PARTIALLY_COVERED": "warn",
        "NOT_COVERED": "fail",
        "QUESTION_REQUIRED": "info",
        "CONFLICTING": "fail",
        "BLOCKED": "warn",
        "OUT_OF_SCOPE": "neutral",
        "SUPERSEDED": "neutral",
        "DEFERRED": "neutral",
        "UNASSESSED": "neutral",
    },
    "severity": {"critical": "fail", "high": "fail", "medium": "warn", "low": "info", "info": "neutral"},
    "crit_status": {
        "confirmed": "pass",
        "proposed": "info",
        "blocked": "warn",
        "out_of_scope": "neutral",
        "superseded": "neutral",
    },
    "field_state": {"confirmed": "pass", "proposed": "info", "inferred": "info", "unknown": "warn"},
    "cmp_relation": {
        "equivalent": "pass",
        "split": "info",
        "merge": "info",
        "overlap": "warn",
        "divergent": "fail",
        "conflicting": "fail",
    },
    "rating": {"supported": "pass", "concern": "warn", "unknown": "neutral", "not_applicable": "neutral"},
    "task_suff": {"sufficient": "pass", "insufficient": "fail", "not_applicable": "neutral"},
}
ICON_FOR_TONE = {
    "pass": "check",
    "fail": "x",
    "warn": "alert",
    "info": "info",
    "neutral": "dot",
    "accent": "dot",
}
GATE_ICON = {"PASS": "check", "FAIL": "x", "BLOCKED": "lock", "NOT_RUN": "clock", "NOT_APPLICABLE": "minus"}
DISP_COLOR = {
    "COVERED": "pass",
    "PARTIALLY_COVERED": "warn",
    "NOT_COVERED": "fail",
    "QUESTION_REQUIRED": "info",
    "CONFLICTING": "c7",
    "BLOCKED": "c6",
    "OUT_OF_SCOPE": "neutral",
    "SUPERSEDED": "c4",
    "DEFERRED": "c5",
    "UNASSESSED": "neutral",
}
TYPE_COLOR = {
    "epic": "c4",
    "feature": "c5",
    "story": "c2",
    "enabler": "c6",
    "spike": "c7",
    "bug": "fail",
    "task": "c3",
}
SEV_ORDER = ["critical", "high", "medium", "low", "info"]
CONTENT_GATES = ("G02", "G03", "G04", "G05", "G06", "G07", "G08", "G09", "G14")
INTEGRATION_GATES = ("G12", "G17", "G18")

ICONS = {
    "check": '<path d="M4 12.5l5 5L20 6.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "alert": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.5v.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.01"/>',
    "dot": '<circle cx="12" cy="12" r="4"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "minus": '<path d="M6 12h12"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "chev": '<path d="M9 6l6 6-6 6"/>',
    "back": '<path d="M15 6l-6 6 6 6"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 00-1-1H5a1 1 0 00-1 1v10a1 1 0 001 1h3"/>',
    "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "print": '<path d="M7 9V4h10v5"/><rect x="4" y="9" width="16" height="8" rx="2"/><path d="M7 14h10v6H7z"/>',
    "link": '<path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1"/>',
    "home": '<path d="M4 11l8-7 8 7v9H4z"/><path d="M10 20v-6h4v6"/>',
    "layers": '<path d="M12 4l9 5-9 5-9-5z"/><path d="M3 14l9 5 9-5"/>',
    "target": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 12h.01"/>',
    "flag": '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "file": '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
    "package": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5L12 12l8-4.5M12 12v9"/>',
    "code": '<path d="M9 8l-4 4 4 4M15 8l4 4-4 4"/>',
    "compare": '<path d="M7 4v16M17 4v16"/><path d="M3 8h8M13 16h8"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01"/>',
    "tree": '<path d="M5 4v16M5 8h6M5 16h6"/><rect x="11" y="5.5" width="8" height="5" rx="1"/><rect x="11" y="13.5" width="8" height="5" rx="1"/>',
    "sidebar": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9 4.5v15"/>',
}


@cache
def _asset(name: str) -> str:
    return resources.files("pbd.render").joinpath("assets", name).read_text(encoding="utf-8")


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _hash(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def _json_block(value: Any) -> str:
    """JSON safe to embed in <script type=application/json> or <pre> (no tag breakout)."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _claim_link(key: str) -> str:
    return f'<a href="#claim-{_e(key)}" class="mono">{_e(key)}</a>'


def _en_li(text: str) -> str:
    """Runtime limitation messages are English data; mark them so assistive tech reads them right."""
    return f'<li lang="en">{_e(text)}</li>'


def icon(name: str, cls: str = "") -> str:
    return f'<svg class="i {cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


def _sprite() -> str:
    symbols = "".join(
        f'<symbol id="i-{k}" viewBox="0 0 24 24">{v}</symbol>' for k, v in sorted(ICONS.items())
    )
    return f'<svg width="0" height="0" class="sr-only" aria-hidden="true">{symbols}</svg>'


class R:
    """Render context: translator, key maps and markup helpers bound to one report."""

    def __init__(self, ui_locale: str, keys: dict[str, str] | None = None) -> None:
        self.t = Translator(ui_locale)
        self.locale = ui_locale
        self.keys = keys or {}
        self._tip = 0

    # ---- text with live i18n hooks
    def _resolve(self, params: dict[str, Any]) -> dict[str, Any]:
        out = {}
        for k, v in params.items():
            out[k] = self.t(v["i18n"], **self._resolve(v.get("p", {}))) if isinstance(v, dict) else v
        return out

    def T(self, key: str, tag: str = "span", cls: str = "", **params: Any) -> str:
        text = self.t(key, **self._resolve(params))
        p = f" data-i18n-p='{_e(json.dumps(params, ensure_ascii=False, sort_keys=True))}'" if params else ""
        c = f' class="{cls}"' if cls else ""
        return f'<{tag}{c} data-i18n="{_e(key)}"{p}>{_e(text)}</{tag}>'

    def attr(self, *pairs: tuple[str, str], **params: Any) -> str:
        """Translated attributes (placeholder, aria-label...) that follow the interface language."""
        parts = [f'{a}="{_e(self.t(k, **params))}"' for a, k in pairs]
        hook = ";".join(f"{a}:{k}" for a, k in pairs)
        p = f" data-i18n-p='{_e(json.dumps(params, ensure_ascii=False, sort_keys=True))}'" if params else ""
        return " ".join(parts) + f' data-i18n-attr="{_e(hook)}"' + p

    def E(self, group: str, code: Any) -> str:
        key = f"enum.{group}.{code}"
        return self.T(key) if self.t.has(key) else _e(code)

    def pill(self, group: str, code: Any, tone: str | None = None, ico: str | None = None) -> str:
        tone = tone or TONES.get(group, {}).get(str(code), "neutral")
        name = (
            ico
            or (GATE_ICON if group == "gate_status" else {}).get(str(code))
            or ICON_FOR_TONE.get(tone, "dot")
        )
        return f'<span class="pill tone-{tone}">{icon(name)}{self.E(group, code)}</span>'

    def type_tag(self, itype: str) -> str:
        return f'<span class="type ty-{_e(itype)}">{self.E("type", itype)}</span>'

    def tip(self, key: str, **params: Any) -> str:
        self._tip += 1
        tid = f"tip-{self._tip}"
        return (
            f'<span class="tip"><button type="button" aria-describedby="{tid}" {self.attr(("aria-label", "a11y.info"))}>'
            f'{icon("info", "sm")}</button><span role="tooltip" id="{tid}">{self.T(key, **params)}</span></span>'
        )

    def key(self, pbd_id: str) -> str:
        return self.keys.get(pbd_id, pbd_id)

    def copy_btn(self, value: str, label_key: str = "actions.copy_id", link: bool = False) -> str:
        extra = " data-copy-link" if link else ""
        return (
            f'<button type="button" class="copy" data-copy="{_e(value)}"{extra} {self.attr(("aria-label", label_key))}>'
            f"{icon('link' if link else 'copy', 'sm')}{self.T(label_key)}</button>"
        )


# ------------------------------------------------------------------------------------ primitives
def _legend_bar(r: R, rows: list[tuple[str, str, int, str]], total: int, goto: str | None = None) -> str:
    """Stacked bar (SVG rect widths, no inline style) + interactive legend. rows: (group, code, n, color)."""
    if total <= 0 or not rows:
        return f'<p class="empty">{r.T("chart.empty")}</p>'
    x = 0.0
    rects = []
    for _, _, n, color in rows:
        w = 1000 * n / total
        rects.append(f'<rect class="fill-{color}" x="{x:.2f}" y="0" width="{w:.2f}" height="12"/>')
        x += w
    summary = ", ".join(f"{r.t.enum(g, c)}: {n}" for g, c, n, _ in rows)
    svg = (
        f'<svg class="bar" viewBox="0 0 1000 12" preserveAspectRatio="none" role="img" '
        f'aria-label="{_e(summary)}">{"".join(rects)}</svg>'
    )
    items = []
    for group, code, n, color in rows:
        inner = (
            f'<span class="sw bg-{color}" aria-hidden="true"></span>{r.E(group, code)}'
            f'<span class="n">{n}</span>'
        )
        if goto:
            items.append(f'<li><button type="button" data-goto="{_e(goto)}|{_e(code)}">{inner}</button></li>')
        else:
            items.append(f'<li><span class="row">{inner}</span></li>')
    return f'{svg}<ul class="legend" {r.attr(("aria-label", "chart.legend"))}>{"".join(items)}</ul>'


def _hbars(r: R, rows: list[tuple[str, str, int, str]]) -> str:
    peak = max((n for *_, n, _c in rows), default=0)
    if not peak:
        return f'<p class="empty">{r.T("chart.empty")}</p>'
    out = []
    for group, code, n, color in rows:
        w = 100 * n / peak
        out.append(
            f'<div class="hbar"><span>{r.E(group, code)}</span><svg viewBox="0 0 100 8" preserveAspectRatio="none" '
            f'aria-hidden="true"><rect class="fill-{color}" x="0" y="0" width="{w:.2f}" height="8"/></svg>'
            f'<span class="n">{n}</span></div>'
        )
    return f'<div class="hbars">{"".join(out)}</div>'


def _metric(r: R, label: str, value: str, detail: str, tip_key: str | None = None, **tip_params: Any) -> str:
    tip = r.tip(tip_key, **tip_params) if tip_key else ""
    return (
        f'<div class="panel metric"><span class="l">{label}{tip}</span><span class="v">{value}</span>'
        f'<span class="d">{detail}</span></div>'
    )


def _frac(a: int, b: int) -> str:
    return f"{a}<small>/{b}</small>"


def _view(vid: str, r: R, title_key: str, desc_key: str | None, body: str, actions: str = "") -> str:
    desc = r.T(desc_key, tag="p") if desc_key else ""
    return (
        f'<section class="view" id="{vid}" aria-labelledby="h-{vid}"><header><div>'
        f'<h2 id="h-{vid}">{r.T(title_key)}</h2>{desc}</div>{actions}</header>{body}</section>'
    )


def _filter_select(
    r: R, target: str, attr: str, label_key: str, options: list[tuple[str, str]], sel_id: str
) -> str:
    opts = "".join(f'<option value="{_e(v)}">{lab}</option>' for v, lab in options)
    return (
        f'<label class="sr-only" for="{sel_id}">{r.T(label_key)}</label>'
        f'<select class="ctl" id="{sel_id}" data-filter-for="{_e(target)}" data-attr="{_e(attr)}">'
        f'<option value="">{r.T(label_key)}: {r.T("ex.filter.any")}</option>{opts}</select>'
    )


def _opt(r: R, group: str, code: str) -> str:
    return r.t.enum(group, code)


# ------------------------------------------------------------------------------------ view model
def _readiness(gates: dict[str, dict[str, Any]], ids: tuple[str, ...]) -> str:
    states = [gates[g]["status"] for g in ids if g in gates]
    applicable = [s for s in states if s != "NOT_APPLICABLE"]
    if not applicable:
        return "na"
    if "FAIL" in applicable:
        return "fail"
    if any(s in ("BLOCKED", "NOT_RUN") for s in applicable):
        return "blocked"
    return "pass"


READY_TONE = {"pass": "pass", "fail": "fail", "blocked": "warn", "na": "neutral"}
READY_ICON = {"pass": "check", "fail": "x", "blocked": "lock", "na": "minus"}


def _gate_explain_key(r: R, g: dict[str, Any]) -> str:
    specific = f"gx.{g['id']}.{g['status']}"
    return specific if r.t.has(specific) else f"gx.{g['status']}"


# ------------------------------------------------------------------------------------ overview
def _overview(r: R, ctx: dict[str, Any], mode: str) -> str:
    backlog, metrics, gate_rows = ctx["backlog"], ctx["metrics"], ctx["gates"]["gates"]
    gates = {g["id"]: g for g in gate_rows}
    n_src = len(backlog["sources"])
    src_phrase = {"i18n": "ov.sources", "p": {"n": n_src}}
    headline = r.T(
        f"ov.headline.{mode if mode in ('audit',) else 'generate'}",
        tag="p",
        cls="headline",
        items=metrics["items"]["total"],
        criteria=metrics["criteria"]["total"],
        sources=src_phrase,
    )
    core = [g for g in gate_rows if g["id"] not in INTEGRATION_GATES]
    c = Counter(g["status"] for g in core)
    if c["FAIL"]:
        state = r.pill("gate_status", "FAIL") + r.T(
            "ov.state.attention", fail=c["FAIL"], blocked=c["BLOCKED"] + c["NOT_RUN"]
        )
    elif c["BLOCKED"] or c["NOT_RUN"]:
        state = r.pill("gate_status", "BLOCKED") + r.T(
            "ov.state.blocked", blocked=c["BLOCKED"] + c["NOT_RUN"]
        )
    else:
        state = r.pill("gate_status", "PASS") + r.T("ov.state.ok")
    audit_note = (
        f'<div class="banner tone-info">{icon("info")}{r.T("ov.audit_note")}</div>' if mode == "audit" else ""
    )
    # readiness
    ready_rows = []
    for key, ids in (
        ("backlog", CONTENT_GATES),
        ("sources", ("G01",)),
        ("review", ("G13",)),
        ("integration", INTEGRATION_GATES),
    ):
        state_code = _readiness(gates, ids)
        tone = READY_TONE[state_code]
        links = " ".join(f'<a href="#gate-{g}" class="mono">{g}</a>' for g in ids if g in gates)
        ready_rows.append(
            f'<div><h4>{r.T(f"ov.ready.{key}")}<span class="pill tone-{tone}">{icon(READY_ICON[state_code])}'
            f"{r.T(f'ov.ready.state.{state_code}')}</span></h4>{r.T(f'ov.ready.{key}.d', tag='p')}<p>{links}</p></div>"
        )
    readiness = f'<section class="block"><h3>{r.T("ov.readiness")}</h3><div class="ready">{"".join(ready_rows)}</div></section>'
    # metrics
    cov = metrics["coverage"]
    g02 = gates.get("G02", {}).get("denominator") or {}
    br = g02.get("breakdown") or {}
    handled = cov["total"] - sum(br.get(k, 0) for k in ("not_covered", "partially_covered", "blocked"))
    src_m = metrics["sources"]
    mt = [
        _metric(r, r.T("m.items"), str(metrics["items"]["total"]), r.T("m.items.d"), None),
        _metric(
            r,
            r.T("m.criteria"),
            str(metrics["criteria"]["total"]),
            r.T("m.criteria.d", proposed=metrics["criteria"]["proposed"]),
        ),
        _metric(
            r,
            r.T("m.full_cov"),
            _frac(cov["covered"], cov["total"]),
            r.T("m.denominator", what={"i18n": "m.den.inventory"}),
            "m.full_cov.d",
        ),
        _metric(
            r,
            r.T("m.handled"),
            _frac(handled, cov["total"]) if g02 else "—",
            r.T("m.denominator", what={"i18n": "m.den.inventory"}),
            "m.handled.d",
        ),
        _metric(
            r,
            r.T("m.members"),
            _frac(src_m["members_read"], src_m["members_total"]),
            r.T("m.denominator", what={"i18n": "m.den.members"}),
            "m.members.d",
        ),
        _metric(r, r.T("m.findings"), str(metrics["findings"]["total"]), r.T("m.findings.d")),
        _metric(
            r,
            r.T("m.questions"),
            str(metrics["questions"]["open"]),
            r.T("m.questions.d", blocking=metrics["questions"]["blocking"]),
        ),
    ]
    metric_html = f'<section class="block"><h3>{r.T("ov.metrics")}</h3><div class="metrics">{"".join(mt)}</div></section>'
    # charts
    obs = Counter(o["disposition"] for o in ctx["review"].get("independent_obligations", []))
    disp_rows = [("disposition", d, obs[d], DISP_COLOR.get(d, "neutral")) for d in DISP_COLOR if obs[d]]
    by_type = metrics["items"]["by_type"]
    type_rows = [("type", t, by_type[t], TYPE_COLOR.get(t, "neutral")) for t in TYPE_COLOR if by_type.get(t)]
    sev = metrics["findings"]["by_severity"]
    sev_rows = [
        (
            "severity",
            s,
            sev[s],
            {"critical": "fail", "high": "fail", "medium": "warn", "low": "info"}.get(s, "neutral"),
        )
        for s in SEV_ORDER
        if sev.get(s)
    ]
    charts = (
        f'<div class="panel chart"><h4>{r.T("ov.coverage")}<span>{r.T("m.denominator", what={"i18n": "m.den.inventory"})} · {cov["total"]}</span></h4>'
        f"{_legend_bar(r, disp_rows, cov['total'], 'requirements|ob-disp')}</div>"
        f'<div class="panel chart"><h4>{r.T("ov.composition")}<span>{metrics["items"]["total"]}</span></h4>'
        f"{_legend_bar(r, type_rows, metrics['items']['total'], 'backlog|f-type')}</div>"
        f'<div class="panel chart"><h4>{r.T("ov.findings_dist")}<span>{metrics["findings"]["total"]}</span></h4>{_hbars(r, sev_rows)}</div>'
    )
    # decisions
    decisions = []
    for q in backlog["questions"]:
        if q["status"] == "open" and q["blocking"]:
            decisions.append(
                f'<li>{r.pill("severity", "high", "fail", "flag")}<a href="#q-{_e(q["id"])}" lang="{_e(backlog["language"])}">{_e(q["text"])}</a></li>'
            )
    for f in sorted(backlog["findings"], key=lambda f: SEV_ORDER.index(f["severity"])):
        if f["severity"] in ("critical", "high"):
            decisions.append(
                f'<li>{r.pill("severity", f["severity"])}<a href="#f-{_e(f["id"])}" lang="{_e(backlog["language"])}">{_e(f["expected"])}</a></li>'
            )
    for q in backlog["questions"]:
        if q["status"] == "open" and not q["blocking"]:
            decisions.append(
                f'<li>{icon("info")}<a href="#q-{_e(q["id"])}" lang="{_e(backlog["language"])}">{_e(q["text"])}</a></li>'
            )
    blocking = sum(1 for q in backlog["questions"] if q["status"] == "open" and q["blocking"])
    dec_html = (
        f'<div class="panel"><h4>{r.T("ov.decisions")}<a href="#findings">{r.T("ov.blocking_q", n=blocking)}</a></h4>'
        + (
            f'<ul class="decisions">{"".join(decisions)}</ul>'
            if decisions
            else f'<p class="empty">{r.T("ov.decisions.none")}</p>'
        )
        + "</div>"
    )
    unproven = [
        f'<li><a href="#gate-{_e(g["id"])}">{_e(g["id"])}</a> {r.E("gate", g["id"])} — {r.E("gate_status", g["status"])}: {r.T(_gate_explain_key(r, g))}</li>'
        for g in gate_rows
        if g["status"] in ("BLOCKED", "NOT_RUN")
    ] + [_en_li(x) for x in ctx.get("limitations", [])]
    unp_html = (
        f'<div class="panel"><h4>{r.T("ov.unproven")}</h4>'
        + (
            f'<ul class="plain">{"".join(unproven)}</ul>'
            if unproven
            else f'<p class="empty">{r.T("common.none")}</p>'
        )
        + "</div>"
    )
    body = (
        f'{headline}<p class="state">{state}</p>{audit_note}'
        f'<div class="ov-grid"><div class="stack">{readiness}{metric_html}</div>'
        f'<div class="stack">{dec_html}{charts}{unp_html}</div></div>'
    )
    return _view("overview", r, "nav.overview", None, body)


# ------------------------------------------------------------------------------------ explorer
def _criterion_body(c: dict[str, Any], style: str, language: str) -> str:
    lab = labels(language)
    if style == "gherkin" and (c.get("condition") or c.get("trigger")):
        lines = []
        if c.get("condition"):
            lines.append(f"<strong>{_e(lab['given'])}</strong> {inline(c['condition'])}")
        if c.get("trigger"):
            lines.append(f"<strong>{_e(lab['gwhen'])}</strong> {inline(c['trigger'])}")
        for i, outcome in enumerate(c["expected_outcomes"]):
            lines.append(f"<strong>{_e(lab['then'] if i == 0 else lab['and'])}</strong> {inline(outcome)}")
        return "<br>".join(lines)
    return inline(criterion_sentence(c))


def _item_text(item: dict[str, Any], key: str, crits: list[dict[str, Any]]) -> str:
    desc = strip_html(item.get("description", {}).get("value", ""))
    parts = [item["id"], key, item["title"], desc]
    parts += [c.get("visible_id", "") + " " + criterion_sentence(c) for c in crits]
    parts += [ref.get("native_id", "") for ref in item.get("external_refs", [])]
    return " ".join(p for p in parts if p)


def _explorer(r: R, ctx: dict[str, Any]) -> str:
    backlog, review = ctx["backlog"], ctx["review"]
    lang = backlog["language"]
    rev_items = {e["key"]: e for e in review.get("items", [])}
    rev_crits = {e["key"]: e for e in review.get("criteria", [])}
    by_parent = criteria_by_parent(backlog)
    items = {i["id"]: i for i in backlog["items"]}
    order = tree_order(backlog)
    children: dict[str | None, list[dict[str, Any]]] = {}
    for item in order:
        children.setdefault(item["parent"], []).append(item)
    claims = {c["id"]: c for c in backlog["claims"]}
    findings_by: dict[str, list[dict[str, Any]]] = {}
    for f in backlog["findings"]:
        for a in f["affects"]:
            findings_by.setdefault(a, []).append(f)
    questions_by: dict[str, list[dict[str, Any]]] = {}
    for q in backlog["questions"]:
        for a in q["affects"]:
            questions_by.setdefault(a, []).append(q)
    rels_by: dict[str, list[dict[str, Any]]] = {}
    for rel in backlog["relations"]:
        rels_by.setdefault(rel["source"], []).append(rel)
        if isinstance(rel["target"], str):
            rels_by.setdefault(rel["target"], []).append(rel)
    depth: dict[str, int] = {}
    for item in order:
        depth[item["id"]] = 0 if not item["parent"] else depth.get(item["parent"], 0) + 1

    def row_attrs(item: dict[str, Any]) -> str:
        k = r.key(item["id"])
        rev = rev_items.get(k, {})
        crits = by_parent.get(item["id"], [])
        return (
            f'data-id="{_e(item["id"])}" data-type="{_e(item["type"])}" data-verdict="{_e(rev.get("verdict", ""))}" '
            f'data-support="{_e(rev.get("source_support", ""))}" data-origin="{_e(item["origin"])}" '
            f'data-text="{_e(_item_text(item, k, crits))}"'
        )

    def tree_li(item: dict[str, Any]) -> str:
        k = r.key(item["id"])
        rev = rev_items.get(k, {})
        kids = children.get(item["id"], [])
        n_ac = len(by_parent.get(item["id"], []))
        tone = TONES["verdict"].get(rev.get("verdict", ""), "")
        dot = (
            f'<span class="dot tone-{tone}" title="{_e(r.t.enum("verdict", rev["verdict"]))}"></span>'
            if tone
            else ""
        )
        tw = (
            f'<button type="button" class="tw" aria-expanded="true" {r.attr(("aria-label", "a11y.expand_item"), label=item["title"])}>{icon("chev", "sm")}</button>'
            if kids
            else '<span class="tw leaf" aria-hidden="true"></span>'
        )
        sub = f"<ul>{''.join(tree_li(c) for c in kids)}</ul>" if kids else ""
        return (
            f'<li {row_attrs(item)} data-depth="{depth[item["id"]]}"><div class="row">{tw}'
            f'<a class="lbl" href="#item-{_e(item["id"])}" data-select="{_e(item["id"])}">'
            f'<span class="type ty-{_e(item["type"])}" aria-hidden="true"></span><span class="k">{_e(k)}</span>'
            f'<span class="t" lang="{_e(lang)}">{_e(item["title"])}</span></a>'
            + (f'<span class="ac">{n_ac}</span>' if n_ac else "")
            + f"{dot}</div>{sub}</li>"
        )

    tree = "".join(tree_li(i) for i in children.get(None, []))
    trows = "".join(
        f'<tr {row_attrs(i)}><td><a href="#item-{_e(i["id"])}" data-select="{_e(i["id"])}" class="mono">{_e(r.key(i["id"]))}</a></td>'
        f'<td>{r.type_tag(i["type"])}</td><td lang="{_e(lang)}">{_e(i["title"])}</td>'
        f'<td class="mono">{_e(r.key(i["parent"])) if i["parent"] else "—"}</td>'
        f"<td>{r.pill('verdict', rev_items[r.key(i['id'])]['verdict']) if rev_items.get(r.key(i['id']), {}).get('verdict') else '—'}</td>"
        f"<td>{len(by_parent.get(i['id'], []))}</td></tr>"
        for i in order
    )
    table = (
        f'<div class="tablewrap" id="table-wrap" hidden><table class="grid" id="itable"><thead><tr>'
        f"<th>{r.T('col.key')}</th><th>{r.T('col.type')}</th><th>{r.T('col.title')}</th><th>{r.T('col.parent')}</th>"
        f"<th>{r.T('col.verdict')}</th><th>{r.T('col.criteria')}</th></tr></thead><tbody>{trows}</tbody></table></div>"
    )

    def opts(group: str, values: list[str]) -> str:
        return "".join(f'<option value="{_e(v)}">{_e(r.t.enum(group, v))}</option>' for v in values)

    types = [t for t in TYPE_COLOR if any(i["type"] == t for i in backlog["items"])]
    verdicts = sorted({e["verdict"] for e in review.get("items", [])})
    supports = sorted({e["source_support"] for e in review.get("items", [])})
    origins = sorted({i["origin"] for i in backlog["items"]})

    def fsel(name: str, label_key: str, group: str, values: list[str], sid: str) -> str:
        if not values:
            return ""
        return (
            f'<label class="sr-only" for="{sid}">{r.T(label_key)}</label><select class="ctl" id="{sid}" data-xfilter="{name}">'
            f'<option value="">{r.T(label_key)}: {r.T("ex.filter.any")}</option>{opts(group, values)}</select>'
        )

    max_depth = max(depth.values(), default=0)
    level_type = {depth[i["id"]] + 1: i["type"] for i in reversed(order)}  # first item type per depth
    level_opts = "".join(
        f'<option value="{n}">{_e(r.t.enum("type", level_type[n]))}</option>'
        for n in range(1, max_depth + 2)
        if n in level_type
    )
    toolbar = (
        f'<div class="toolbar" role="search"><div class="search">{icon("search")}'
        f'<label class="sr-only" for="q">{r.T("ex.search")}</label>'
        f'<input id="q" type="search" autocomplete="off" {r.attr(("placeholder", "ex.search"))}></div>'
        f'<div class="filters">{fsel("type", "ex.filter.type", "type", types, "f-type")}'
        f"{fsel('verdict', 'ex.filter.verdict', 'verdict', verdicts, 'f-verdict')}"
        f"{fsel('support', 'ex.filter.support', 'support', supports, 'f-support')}"
        f"{fsel('origin', 'ex.filter.origin', 'origin', origins, 'f-origin') if len(origins) > 1 else ''}"
        f'<button type="button" class="ctl" id="ex-clear">{r.T("ex.clear")}</button></div></div>'
        f'<div class="chips" id="chips" aria-live="polite"></div>'
        f'<div class="resultbar"><span id="ex-count" aria-live="polite">{r.T("ex.count", n=len(order))} {r.T("ex.count_of", total=len(order))}</span>'
        f'<span class="seg" role="group"><button type="button" data-xview="tree" aria-pressed="true">{icon("tree", "sm")}{r.T("ex.view.tree")}</button>'
        f'<button type="button" data-xview="table" aria-pressed="false">{icon("list", "sm")}{r.T("ex.view.table")}</button></span></div>'
        f'<div class="resultbar"><span><label for="ex-level">{r.T("ex.level")}</label> '
        f'<select class="ctl" id="ex-level"><option value="99">—</option>{level_opts}</select></span>'
        f'<span><button type="button" class="ctl" id="ex-expand">{r.T("ex.expand")}</button> '
        f'<button type="button" class="ctl" id="ex-collapse">{r.T("ex.collapse")}</button></span></div>'
    )
    master = (
        f'<div class="panel master">{toolbar}<div class="scroll"><div id="tree-wrap"><ul class="tree" id="tree">{tree}</ul></div>{table}'
        f'<p class="empty" id="ex-none" hidden>{r.T("ex.none")}</p></div></div>'
    )

    def trace(refs: list[str]) -> str:
        out = []
        for ref in refs:
            c = claims.get(ref)
            if not c:
                continue
            for ev in c["evidence"]:
                loc = ev.get("locator", {})
                line = loc.get("line_start")
                end = loc.get("line_end")
                span = f"{line}" + (f"–{end}" if end not in (None, line) else "")
                out.append(
                    f'<li><a href="#claim-{_e(r.key(ref))}" class="mono">{_e(r.key(ref))}</a> <span lang="{_e(lang)}">{_e(c["text"])}</span><br>'
                    f'<span class="loc">{_e(loc.get("member"))}:{_e(span)}</span> <span class="quote">{_e(ev.get("summary", ""))}</span></li>'
                )
        return '<ul class="plain">' + "".join(out) + "</ul>" if out else ""

    def article(item: dict[str, Any]) -> str:
        k = r.key(item["id"])
        rev = rev_items.get(k, {})
        crits = by_parent.get(item["id"], [])
        style = item.get("acceptance_style", "list")
        anc = []
        p = item["parent"]
        while p:
            anc.append(items[p])
            p = items[p]["parent"]
        anc_html = " / ".join(
            f'<a href="#item-{_e(a["id"])}" data-select="{_e(a["id"])}" lang="{_e(lang)}">{_e(a["title"])}</a>'
            for a in reversed(anc)
        )
        meta = [r.type_tag(item["type"])]
        if rev.get("verdict"):
            meta.append(r.pill("verdict", rev["verdict"]))
        if rev.get("source_support"):
            meta.append(r.pill("support", rev["source_support"]))
        if item["origin"] != "generated":
            meta.append(f'<span class="tag">{r.E("origin", item["origin"])}</span>')
        ext = "".join(
            f"<span>{r.T('it.external')}: <code>{_e(x['native_id'])}</code></span>"
            for x in item.get("external_refs", [])
        )
        head = (
            f'<header><button type="button" class="ctl back">{icon("back", "sm")}{r.T("a11y.back")}</button>'
            + (f'<div class="ancestors">{anc_html}</div>' if anc_html else "")
            + f'<div class="meta">{"".join(meta)}</div><h3 lang="{_e(lang)}">{_e(item["title"])}</h3>'
            f'<div class="idline"><code>{_e(k)}</code><code>{_e(item["id"])}</code>{ext}{r.copy_btn(item["id"])}'
            f"{r.copy_btn('item-' + item['id'], 'actions.copy_link', link=True)}</div></header>"
        )
        secs = []
        desc = sanitize_html(item.get("description", {}).get("value", ""))
        if desc:
            secs.append(
                f'<div class="sec"><h4>{r.T("it.description")}</h4><div class="rich" lang="{_e(lang)}">{desc}</div></div>'
            )
        if crits:
            lis = []
            for c in crits:
                ck = r.key(c["id"])
                cr = rev_crits.get(ck, {})
                links = " ".join(
                    f'<a href="#claim-{_e(r.key(x))}" class="mono">{_e(r.key(x))}</a>'
                    for x in c["claim_refs"]
                )
                cmeta = [r.pill("crit_status", c["status"])]
                if cr.get("verdict"):
                    cmeta.append(r.pill("verdict", cr["verdict"]))
                if cr.get("source_support"):
                    cmeta.append(r.pill("support", cr["source_support"]))
                notes = f'<span lang="{_e(lang)}">{_e(cr.get("notes", ""))}</span>' if cr.get("notes") else ""
                rationale = (
                    f'<span lang="{_e(lang)}">{_e(c.get("rationale", ""))}</span>'
                    if c.get("rationale") and not c["claim_refs"]
                    else ""
                )
                lis.append(
                    f'<li id="crit-{_e(c["id"])}"><span class="cid">{_e(c.get("visible_id", ""))}</span>'
                    f'<div class="rich" lang="{_e(lang)}">{_criterion_body(c, style, lang)}</div>'
                    f'<div class="cmeta">{"".join(cmeta)}{links}{notes}{rationale}</div></li>'
                )
            secs.append(
                f'<div class="sec"><h4>{r.T("it.acceptance")}</h4><ol class="criteria">{"".join(lis)}</ol></div>'
            )
        kids = children.get(item["id"], [])
        if kids:
            links = "".join(
                f'<a href="#item-{_e(c["id"])}" data-select="{_e(c["id"])}"><span class="type ty-{_e(c["type"])}" aria-hidden="true"></span>'
                f'<span lang="{_e(lang)}">{_e(c["title"])}</span></a>'
                for c in kids
            )
            secs.append(
                f'<div class="sec"><h4>{r.T("it.children")}</h4><div class="links">{links}</div></div>'
            )
        if item.get("fields"):
            frows = "".join(
                f'<tr><td>{r.E("field", n)}<br><span class="fref">{_e(n)}</span></td><td>{_e(v.get("value", "—"))}</td>'
                f'<td>{r.pill("field_state", v["state"])}</td><td lang="{_e(lang)}">{_e(v.get("rationale", ""))}</td></tr>'
                for n, v in sorted(item["fields"].items())
            )
            secs.append(
                f'<div class="sec"><h4>{r.T("it.fields")}</h4><div class="tablewrap"><table class="grid"><thead><tr>'
                f"<th>{r.T('col.field')}</th><th>{r.T('col.value')}</th><th>{r.T('col.state')}</th><th>{r.T('col.rationale')}</th>"
                f"</tr></thead><tbody>{frows}</tbody></table></div></div>"
            )
        tr = trace(item.get("claim_refs", []))
        note = ""
        if item["origin"] == "imported":
            note = f'<p class="nojs-note">{r.T("it.imported_note")}</p>'
        if tr or item.get("technical_rationale") or item["origin"] == "imported":
            rat = (
                f'<p><strong>{r.T("it.rationale")}:</strong> <span lang="{_e(lang)}">{_e(item["technical_rationale"])}</span></p>'
                if item.get("technical_rationale")
                else ""
            )
            secs.append(
                f'<div class="sec"><h4>{r.T("it.trace")}</h4>{tr or r.T("it.no_trace", tag="p")}{rat}'
                + (f'<p class="d">{r.T("it.imported_note")}</p>' if item["origin"] == "imported" else "")
                + "</div>"
            )
        del note
        rels = rels_by.get(item["id"], [])
        if rels:
            rl = "".join(
                f"<li>{_e(r.key(x['source']))} → {r.E('relation', x['type'])} → "
                f"{_e(r.key(x['target']) if isinstance(x['target'], str) else x['target'])} "
                f'{r.pill("rel_status", x["status"], "neutral")} <span lang="{_e(lang)}">{_e(x["reason"])}</span></li>'
                for x in rels
            )
            secs.append(
                f'<div class="sec"><h4>{r.T("it.dependencies")}</h4><ul class="plain">{rl}</ul></div>'
            )
        if rev:
            inv = rev.get("invest") or {}
            inv_html = "".join(
                f"<div><strong>{r.E('invest', dim)}</strong>{r.pill('rating', v.get('rating', 'unknown'))}"
                f'<span lang="{_e(lang)}">{_e(v.get("note", ""))}</span></div>'
                for dim, v in inv.items()
                if isinstance(v, dict)
            )
            kv = []
            if rev.get("task_sufficiency"):
                kv.append(
                    f"<dt>{r.T('it.tasks_suff')}</dt><dd>{r.pill('task_suff', rev['task_sufficiency'])}</dd>"
                )
            if rev.get("notes"):
                kv.append(f'<dt>{r.T("col.notes")}</dt><dd lang="{_e(lang)}">{_e(rev["notes"])}</dd>')
            secs.append(
                f'<div class="sec"><h4>{r.T("it.review")}</h4>'
                + (f'<dl class="kv">{"".join(kv)}</dl>' if kv else "")
                + (f'<h4>{r.T("it.invest")}</h4><div class="invest">{inv_html}</div>' if inv_html else "")
                + "</div>"
            )
        related_ids = {item["id"], *(c["id"] for c in crits)}
        rel_f = {f["id"]: f for rid in related_ids for f in findings_by.get(rid, [])}
        rel_q = {q["id"]: q for rid in related_ids for q in questions_by.get(rid, [])}
        if rel_f or rel_q:
            links = "".join(
                f'<a href="#f-{_e(f["id"])}">{r.pill("severity", f["severity"])}<span lang="{_e(lang)}">{_e(f["expected"][:90])}</span></a>'
                for f in rel_f.values()
            ) + "".join(
                f'<a href="#q-{_e(q["id"])}">{icon("flag", "sm")}<span lang="{_e(lang)}">{_e(q["text"][:90])}</span></a>'
                for q in rel_q.values()
            )
            secs.append(
                f'<div class="sec"><h4>{r.T("it.findings")}</h4><div class="links">{links}</div></div>'
            )
        tech = (
            f'<details class="tech"><summary>{icon("chev", "sm")}{r.T("it.technical")}</summary><div>'
            f'<pre class="json">{_json_block({"item": item, "criteria": crits})}</pre></div></details>'
        )
        head = head.replace("<h3 ", '<h3 id="t-' + _e(item["id"]) + '" ', 1)
        return (
            f'<article class="panel item" id="item-{_e(item["id"])}" data-id="{_e(item["id"])}" '
            f'aria-labelledby="t-{_e(item["id"])}">{head}{"".join(secs)}{tech}</article>'
        )

    detail = f'<div class="detail" id="detail"><div class="panel placeholder">{r.T("ex.select")}</div>{"".join(article(i) for i in order)}</div>'
    body = f'<p class="nojs-note">{r.T("nojs")}</p><div class="explorer" id="explorer">{master}{detail}</div>'
    return _view("backlog", r, "nav.backlog", None, body)


# ------------------------------------------------------------------------------------ requirements
def _requirements(r: R, ctx: dict[str, Any]) -> str:
    backlog, review = ctx["backlog"], ctx["review"]
    lang = backlog["language"]
    by_id = {s["id"]: s for s in backlog["sources"]}
    work = {
        **{i["id"]: i["id"] for i in backlog["items"]},
        **{c["id"]: c["parent"] for c in backlog["criteria"]},
    }
    by_key = {v: k for k, v in r.keys.items()}

    def work_link(key: str) -> str:
        pid = by_key.get(key)
        if pid is None:
            return f'<span class="mono">{_e(key)}</span>'
        anchor = f"crit-{pid}" if pid in work and work[pid] != pid else f"item-{pid}"
        return f'<a href="#{_e(anchor)}" class="mono">{_e(key)}</a>'

    obs = review.get("independent_obligations", [])
    disp_values = [d for d in DISP_COLOR if any(o["disposition"] == d for o in obs)]
    src_values = sorted({o["locator"].get("source_id", "") for o in obs})
    ob_rows = "".join(
        f'<tr data-row data-disp="{_e(o["disposition"])}" data-src="{_e(o["locator"].get("source_id", ""))}" id="ob-{_e(o["key"])}">'
        f'<td class="mono">{_e(o["key"])}</td><td lang="{_e(lang)}">{_e(o.get("text", ""))}</td>'
        f'<td><span class="quote">{_e(o.get("quote", ""))}</span><br><span class="loc">'
        f"{_e(by_id.get(o['locator'].get('source_id'), {}).get('selector', ''))} · {_e(o['locator'].get('member'))}:{_e(o['locator'].get('line_start'))}</span></td>"
        f"<td>{r.pill('disposition', o['disposition'])}</td>"
        f"<td>{' '.join(work_link(k) for k in o.get('covered_by', [])) or '—'}</td>"
        f"<td>{' '.join(_claim_link(k) for k in o.get('matched_claims', [])) or '—'}</td>"
        f'<td lang="{_e(lang)}">{_e(o.get("rationale", ""))}</td></tr>'
        for o in obs
    )
    filters = _filter_select(
        r,
        "ob-table",
        "disp",
        "rq.filter",
        [(d, _e(_opt(r, "disposition", d))) for d in disp_values],
        "ob-disp",
    ) + (
        _filter_select(
            r,
            "ob-table",
            "src",
            "col.source",
            [(s, _e(by_id.get(s, {}).get("selector", s))) for s in src_values],
            "ob-src",
        )
        if len(src_values) > 1
        else ""
    )
    ob_html = (
        f'<section class="block"><h3>{r.T("rq.obligations")}</h3>{r.T("rq.obligations.d", tag="p", cls="d")}'
        f'<div class="panel"><div class="toolbar">{filters}<span class="d"><span id="ob-table-n">{len(obs)}</span>/{len(obs)}</span></div>'
        f'<div class="tablewrap"><table class="grid" id="ob-table"><thead><tr><th>{r.T("col.key")}</th><th>{r.T("col.obligation")}</th>'
        f"<th>{r.T('col.quote')}</th><th>{r.T('col.disposition')}</th><th>{r.T('col.covered_by')}</th><th>{r.T('col.claim')}</th>"
        f"<th>{r.T('col.rationale')}</th></tr></thead><tbody>{ob_rows}</tbody></table></div></div></section>"
    )
    claims = backlog["claims"]
    cl_rows = "".join(
        f'<tr data-row data-disp="{_e(c["disposition"]["status"])}" id="claim-{_e(r.key(c["id"]))}"><td class="mono">{_e(r.key(c["id"]))}</td>'
        f'<td lang="{_e(lang)}">{_e(c["text"])}</td><td>{r.E("category", c["category"])}</td>'
        f"<td>{r.pill('disposition', c['disposition']['status'])}</td>"
        f"<td>{' '.join(work_link(r.key(x)) for x in c['disposition'].get('covered_by', [])) or '—'}</td>"
        f'<td lang="{_e(lang)}">{_e(c["disposition"].get("rationale", ""))}</td></tr>'
        for c in claims
    )
    c_disp = [d for d in DISP_COLOR if any(c["disposition"]["status"] == d for c in claims)]
    cl_html = (
        f'<section class="block"><h3>{r.T("rq.claims")}</h3>{r.T("rq.claims.d", tag="p", cls="d")}'
        f'<div class="panel"><div class="toolbar">{_filter_select(r, "cl-table", "disp", "rq.filter", [(d, _e(_opt(r, "disposition", d))) for d in c_disp], "cl-disp")}'
        f'<span class="d"><span id="cl-table-n">{len(claims)}</span>/{len(claims)}</span></div>'
        f'<div class="tablewrap"><table class="grid" id="cl-table"><thead><tr><th>{r.T("col.key")}</th><th>{r.T("col.claim")}</th>'
        f"<th>{r.T('col.category')}</th><th>{r.T('col.disposition')}</th><th>{r.T('col.covered_by')}</th><th>{r.T('col.rationale')}</th>"
        f"</tr></thead><tbody>{cl_rows}</tbody></table></div></div></section>"
    )
    dec = backlog.get("decisions", [])
    dec_html = ""
    if dec:
        rows = "".join(
            f'<li><strong class="mono">{_e(r.key(x["id"]))}</strong> {r.pill("decision_status", x["status"], "info")} <span lang="{_e(lang)}">{_e(x["text"])}</span>'
            + (
                f" — {r.T('rq.supersedes')}: "
                + " ".join(
                    f'<a href="#claim-{_e(r.key(s))}" class="mono">{_e(r.key(s))}</a>'
                    for s in x.get("supersedes_claims", [])
                )
                if x.get("supersedes_claims")
                else ""
            )
            + "</li>"
            for x in dec
        )
        dec_html = f'<section class="block"><h3>{r.T("rq.decisions")}</h3><div class="panel"><ul class="plain">{rows}</ul></div></section>'
    return _view("requirements", r, "nav.requirements", None, ob_html + cl_html + dec_html)


# ------------------------------------------------------------------------------------ findings
def _finding_card(r: R, f: dict[str, Any], lang: str, affects_html: str, side: str = "") -> str:
    tone = TONES["severity"].get(f["severity"], "neutral")
    gate = f'<a class="tag" href="#gate-{_e(f["gate"])}">{_e(f["gate"])}</a>' if f.get("gate") else ""
    side_tag = f'<span class="tag">{r.T("cmp.side." + side)}</span>' if side else ""
    more = (
        f'<div><h5>{r.T("fd.why")}</h5><p lang="{_e(lang)}">{_e(f["why"])}</p></div>'
        f'<div><h5>{r.T("fd.impact")}</h5><p lang="{_e(lang)}">{_e(f["impact"])}</p></div>'
        f'<div><h5>{r.T("fd.recommendation")}</h5><p lang="{_e(lang)}">{_e(f["recommendation"])}</p></div>'
    )
    if f.get("decision_needed"):
        more += f'<div><h5>{r.T("fd.decision_needed")}</h5><p lang="{_e(lang)}">{_e(f["decision_needed"])}</p></div>'
    fid = f.get("id") or ""
    return (
        f'<article class="panel finding tone-{tone}" data-row data-sev="{_e(f["severity"])}" id="f-{_e(fid)}">'
        f'<header>{r.pill("severity", f["severity"])}<span class="tag">{r.E("classification", f["classification"])}</span>'
        f'<span class="tag">{r.E("review_status", f.get("review_status", "confirmed"))}</span>{gate}{side_tag}</header>'
        f'<div class="ea"><div><h5>{r.T("fd.expected")}</h5><p lang="{_e(lang)}">{_e(f["expected"])}</p></div>'
        f'<div><h5>{r.T("fd.actual")}</h5><p lang="{_e(lang)}">{_e(f["actual"])}</p></div></div>'
        f'<div class="more">{more}</div><footer><span class="d">{r.T("fd.affects")}:</span> {affects_html}</footer></article>'
    )


def _findings(r: R, ctx: dict[str, Any]) -> str:
    backlog = ctx["backlog"]
    lang = backlog["language"]
    crit_parent = {c["id"]: c["parent"] for c in backlog["criteria"]}

    def link(pid: str) -> str:
        anchor = f"crit-{pid}" if pid in crit_parent else f"item-{pid}"
        return f'<a href="#{_e(anchor)}" class="mono">{_e(r.key(pid))}</a>'

    fs = sorted(backlog["findings"], key=lambda f: (SEV_ORDER.index(f["severity"]), f["id"]))
    sevs = [s for s in SEV_ORDER if any(f["severity"] == s for f in fs)]
    cards = "".join(_finding_card(r, f, lang, " ".join(link(a) for a in f["affects"]) or "—") for f in fs)
    f_html = (
        f'<section class="block"><h3>{r.T("fd.title")}</h3>'
        + (
            f'<div class="toolbar">{_filter_select(r, "fd-cards", "sev", "col.status", [(s, _e(_opt(r, "severity", s))) for s in sevs], "fd-sev")}'
            f'<span class="d"><span id="fd-cards-n">{len(fs)}</span>/{len(fs)}</span></div>'
            f'<div class="cards" id="fd-cards">{cards}</div>'
            if fs
            else f'<div class="panel empty">{r.T("fd.none")}</div>'
        )
        + "</section>"
    )
    qs = [q for q in backlog["questions"]]
    groups = []
    for blocking in (True, False):
        items = [q for q in qs if q["blocking"] == blocking]
        if not items:
            continue
        body = "".join(
            f'<div class="question" id="q-{_e(q["id"])}"><p lang="{_e(lang)}"><strong>{_e(q["text"])}</strong></p>'
            f'<p class="imp"><span>{r.T("q.impact")}:</span> <span lang="{_e(lang)}">{_e(q["impact"])}</span></p>'
            + (
                f'<p class="imp">{r.T("q.options")}: <span lang="{_e(lang)}">{_e(" · ".join(q["options"]))}</span></p>'
                if q.get("options")
                else ""
            )
            + f'<div class="links">{" ".join(link(a) for a in q["affects"] if not a.startswith("PBD-CLM"))}</div></div>'
            for q in items
        )
        head = (
            r.pill("severity", "high", "fail", "flag") + r.T("q.blocking")
            if blocking
            else r.T("q.nonblocking")
        )
        groups.append(f'<div class="qgroup"><h4>{head}</h4><div class="panel">{body}</div></div>')
    q_html = (
        f'<section class="block"><h3>{r.T("q.title")}</h3><div class="banner tone-info">{icon("info")}{r.T("q.decision_note")}</div>'
        + ("".join(groups) or f'<div class="panel empty">{r.T("q.none")}</div>')
        + "</section>"
    )
    return _view("findings", r, "nav.findings", None, f_html + q_html)


# ------------------------------------------------------------------------------------ quality
def _quality(r: R, ctx: dict[str, Any]) -> str:
    gate_rows = ctx["gates"]["gates"]
    statuses = [
        s
        for s in ("FAIL", "BLOCKED", "NOT_RUN", "PASS", "NOT_APPLICABLE")
        if any(g["status"] == s for g in gate_rows)
    ]
    rows = []
    for g in gate_rows:
        den = g.get("denominator") or {}
        den_html = f"{den['examined']}/{den['total']}" if den else "—"
        ev = "".join(
            f'<li><span class="tag">{r.T("qa.kind." + e["type"]) if r.t.has("qa.kind." + e["type"]) else _e(e["type"])}</span>'
            f'<code>{_e(e["ref"])}</code><code title="{_e(e.get("digest", ""))}">{_e(str(e.get("digest", ""))[:19])}…</code>'
            f"{r.copy_btn(str(e.get('digest', '')))}</li>"
            for e in g.get("evidence", [])
        )
        verified = r.T("qa.verified") if g.get("verification") == "verified" else r.T("qa.not_verified")
        breakdown = ", ".join(f"{k}: {v}" for k, v in (den.get("breakdown") or {}).items())
        rows.append(
            f'<details class="gate" id="gate-{_e(g["id"])}" data-row data-status="{_e(g["status"])}"><summary>'
            f'<span class="gid">{r.pill("gate_status", g["status"])}</span><code>{_e(g["id"])}</code>'
            f'<span><span class="nm">{r.E("gate", g["id"])}</span><span class="ex">{r.T(_gate_explain_key(r, g))}</span></span>'
            f'<span class="den">{_e(den_html)}</span>{icon("chev", "sm")}</summary><div>'
            f'<dl class="kv"><dt>{r.T("col.verification")}</dt><dd>{verified}</dd>'
            + (
                f'<dt>{r.T("col.denominator")}</dt><dd>{_e(den_html)} <span class="mono">{_e(den.get("provenance", ""))}</span><br><span class="mono">{_e(breakdown)}</span></dd>'
                if den
                else ""
            )
            + f'<dt>{r.T("qa.runtime_msg")}</dt><dd lang="en"><code>{_e(g["reason"])}</code></dd></dl>'
            + (f'<h4>{r.T("qa.evidence")}</h4><ul class="evidence">{ev}</ul>' if ev else "")
            + "</div></details>"
        )
    body = (
        f'<div class="panel"><div class="toolbar">{_filter_select(r, "gate-list", "status", "qa.filter", [(s, _e(_opt(r, "gate_status", s))) for s in statuses], "qa-status")}'
        f'<span class="d"><span id="gate-list-n">{len(gate_rows)}</span>/{len(gate_rows)}</span></div>'
        f'<div class="gates" id="gate-list">{"".join(rows)}</div></div>'
    )
    lim = ctx.get("limitations", [])
    lim_html = (
        f'<section class="block"><h3>{r.T("qa.limitations")}</h3><div class="panel">'
        + (
            f'<ul class="plain">{"".join(_en_li(x) for x in lim)}</ul>'
            if lim
            else f'<p class="empty">{r.T("qa.none")}</p>'
        )
        + "</div></section>"
    )
    return _view("quality", r, "nav.quality", "qa.d", f'<section class="block">{body}</section>{lim_html}')


def _sources(r: R, ctx: dict[str, Any]) -> str:
    cards = []
    for s in ctx["backlog"]["sources"]:
        tone = "pass" if s["read_status"] == "complete" else "warn"
        members = "".join(
            f'<li><span class="mono">{_e(m["path"])}</span><span>{r.pill("member_status", m["status"], "pass" if m["status"] == "read" else "warn")}</span></li>'
            + (f'<li lang="en"><span class="d">{_e(m["reason"])}</span></li>' if m.get("reason") else "")
            for m in s.get("members", [])
        )
        cards.append(
            f'<article class="panel src" id="src-{_e(s["id"])}"><header><h4 class="mono">{_e(s["selector"])}</h4>'
            f'<div class="meta"><span class="tag">{r.E("authority", s["authority"])}</span>{r.pill("read_status", s["read_status"], tone)}</div>'
            f'<div class="idline"><code>{_e(s["id"])}</code><code title="{_e(s["digest"])}">{_e(s["digest"][:19])}…</code></div></header>'
            f'<ul class="plain members">{members}</ul></article>'
        )
    return _view("sources", r, "nav.sources", "src.d", f'<div class="src-grid">{"".join(cards)}</div>')


def _integration(r: R, ctx: dict[str, Any]) -> str:
    azure = ctx.get("azure")
    if not azure:
        return ""
    lang = ctx["backlog"]["language"]
    rows = []
    for w in azure["work_items"]:
        fields = "".join(
            f'<tr><td class="fref">{_e(k)}</td><td><div class="rich" lang="{_e(lang)}">{sanitize_html(str(v))}</div></td></tr>'
            for k, v in w["fields"].items()
        )
        fields += "".join(
            f'<tr><td class="fref">{_e(k)}</td><td>{r.pill("field_state", "proposed")} {r.T("int.proposed_not_written")}: {_e(v["value"])}</td></tr>'
            for k, v in w.get("proposed_fields_not_written", {}).items()
        )
        rows.append(
            f'<details class="wi-pkg"><summary>{icon("chev", "sm")}<span class="tag">{_e(w["work_item_type"])}</span>'
            f'<code>{_e(r.key(w["pbd_id"]))}</code><span lang="{_e(lang)}">{_e(w["fields"].get("System.Title", ""))}</span></summary>'
            f'<div class="tablewrap"><table class="grid"><thead><tr><th>{r.T("col.field")}</th><th>{r.T("col.value")}</th></tr></thead>'
            f"<tbody>{fields}</tbody></table></div></details>"
        )
    lim = "".join(f'<li lang="en">{_e(x)}</li>' for x in azure.get("limitations", []))
    body = (
        f'<div class="banner tone-warn">{icon("lock")}{r.T("header.local_only")}</div>'
        f'<dl class="kv"><dt>{r.T("int.profile")}</dt><dd><code>{_e(azure["profile"])}</code> — '
        f"{r.T('int.profile_unverified') if not azure.get('profile_verified') else ''}</dd></dl>"
        f'<div class="panel">{"".join(rows)}</div>'
        + (
            f'<section class="block"><h3>{r.T("qa.limitations")}</h3><div class="panel"><ul class="plain">{lim}</ul></div></section>'
            if lim
            else ""
        )
    )
    return _view("integration", r, "int.title", "int.d", body)


def _data(r: R, value: Any, pre_id: str, filename: str, label_key: str) -> str:
    body = (
        f'<div class="panel pad"><p><button type="button" class="ctl primary" data-download="{pre_id}" data-filename="{_e(filename)}">'
        f"{icon('download', 'sm')}{r.T(label_key)}</button></p>"
        f'<details><summary>{r.T("data.show")}</summary><pre class="json" id="{pre_id}">{_json_block(value)}</pre></details></div>'
    )
    return _view("data", r, "data.title", "data.d", body)


# ------------------------------------------------------------------------------------ shell
def _nav(r: R, entries: list[tuple[str, str, str, int | None]]) -> str:
    groups: dict[str, list[str]] = {"product": [], "technical": []}
    for vid, key, ico, count in entries:
        grp = "technical" if vid in ("quality", "sources", "integration", "data") else "product"
        cnt = f'<span class="count">{count}</span>' if count is not None else ""
        groups[grp].append(
            f'<li><a href="#{vid}" data-view="{vid}">{icon(ico)}{r.T(key, cls="label")}{cnt}</a></li>'
        )
    return "".join(
        f"<div><h2>{r.T('nav.group.' + g)}</h2><ul>{''.join(v)}</ul></div>" for g, v in groups.items() if v
    )


def _page(
    r: R,
    *,
    title: str,
    mode: str,
    subtitle: str,
    content_lang: str,
    nav: str,
    views: str,
    version: str,
    synthetic: bool,
) -> str:
    css = _asset("report.css")
    js = _asset("report.js")
    cats = {loc: catalog(loc) for loc in LOCALES}
    csp = (
        f"default-src 'none'; style-src 'sha256-{_hash(css)}'; script-src 'sha256-{_hash(js)}'; img-src data:; "
        "base-uri 'none'; form-action 'none'"
    )
    lang_opts = "".join(
        f'<option value="{loc}"{" selected" if loc == r.locale else ""}>{_e(catalog(loc)["lang.name." + loc])}</option>'
        for loc in LOCALES
    )
    theme_opts = "".join(
        f'<option value="{v}">{_e(r.t("theme." + v))}</option>' for v in ("system", "light", "dark")
    )
    synth = (
        f'<span class="pill tone-warn hide-sm">{icon("alert")}{r.T("header.synthetic")}</span>'
        if synthetic
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="{_e(r.locale)}" class="no-js" data-ui-locale="{_e(r.locale)}" data-content-lang="{_e(content_lang)}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{_e(csp)}">
<meta name="generator" content="pbd {_e(version)}"><meta name="referrer" content="no-referrer">
<title>{_e(title)} — PBD</title><style>{css}</style></head>
<body>{_sprite()}<a class="skip" href="#main">{r.T("a11y.skip")}</a>
<header class="top"><button type="button" class="ctl icon menu-btn" id="menu" aria-controls="side" aria-expanded="false" {r.attr(("aria-label", "a11y.open_nav"))}>{icon("menu")}</button>
<button type="button" class="ctl icon collapse-btn hide-sm" id="collapse" aria-pressed="false" {r.attr(("aria-label", "a11y.collapse_nav"))}>{icon("sidebar")}</button>
<span class="logo" aria-hidden="true">PB</span><div class="proj"><strong lang="{_e(content_lang)}">{_e(title)}</strong><span>{subtitle}</span></div>
<span class="pill tone-accent">{r.T("mode." + mode)}</span>{synth}
<span class="grow"></span><div class="tools">
<label class="sr-only" for="lang-sel">{r.T("lang.label")}</label><select class="ctl lang" id="lang-sel">{lang_opts}</select>
<label class="sr-only" for="theme-sel">{r.T("theme.label")}</label><select class="ctl hide-sm" id="theme-sel">{theme_opts}</select>
<button type="button" class="ctl icon hide-sm" id="print" {r.attr(("aria-label", "actions.print"))}>{icon("print")}</button></div></header>
<div class="layout"><nav class="side" id="side" {r.attr(("aria-label", "a11y.nav"))}>{nav}
<div class="foot"><p>{r.T("header.local_only")}</p><p>{r.T("header.generated_by", version=version)}</p>
<label><input type="checkbox" id="print-tech"> {r.T("print.technical")}</label></div></nav>
<div class="scrim" id="scrim"></div>
<main id="main" tabindex="-1"><nav class="crumbs" {r.attr(("aria-label", "a11y.breadcrumb"))}><span lang="{_e(content_lang)}">{_e(title)}</span>{icon("chev", "sm")}<span id="crumb-view" aria-current="location">{r.T("nav.overview")}</span></nav>
<p class="banner tone-info">{icon("shield")}{r.T("header.privacy")}</p>
{views}</main></div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script type="application/json" id="pbd-i18n">{_json_block(cats)}</script>
<script>{js}</script></body></html>
"""


def render_report(ctx: dict[str, Any]) -> str:
    """Report for generation and audit runs (``ctx`` built by finalize)."""
    backlog = ctx["backlog"]
    mode = ctx.get("mode", "generate")
    ui = resolve_locale(ctx.get("ui_locale") or backlog["language"])
    r = R(ui, ctx["keys"])
    metrics = ctx["metrics"]
    views = [
        _overview(r, ctx, mode),
        _explorer(r, ctx),
        _requirements(r, ctx),
        _findings(r, ctx),
        _quality(r, ctx),
        _sources(r, ctx),
        _integration(r, ctx),
        _data(r, backlog, "canonical", "backlog.json", "actions.download_json"),
    ]
    gates = Counter(g["status"] for g in ctx["gates"]["gates"])
    entries = [
        ("overview", "nav.overview", "home", None),
        ("backlog", "nav.backlog", "layers", metrics["items"]["total"]),
        ("requirements", "nav.requirements", "target", metrics["coverage"]["total"]),
        ("findings", "nav.findings", "flag", metrics["findings"]["total"] + metrics["questions"]["open"]),
        ("quality", "nav.quality", "shield", gates["FAIL"] + gates["BLOCKED"] or None),
        ("sources", "nav.sources", "file", len(backlog["sources"])),
    ]
    if ctx.get("azure"):
        entries.append(("integration", "nav.integration", "package", len(ctx["azure"]["work_items"])))
    entries.append(("data", "nav.data", "code", None))
    subtitle = f"{r.T('header.run')} <code>{_e(backlog['run_id'])}</code> · {r.T('header.profile')} {_e(backlog.get('profile'))}"
    return _page(
        r,
        title=ctx.get("title") or "Product Backlog",
        mode=mode,
        subtitle=subtitle,
        content_lang=backlog["language"],
        nav=_nav(r, entries),
        views="".join(views),
        version=str(ctx.get("version", "")),
        synthetic=bool(backlog.get("synthetic")),
    )


# ------------------------------------------------------------------------------------ comparison
def render_comparison_report(
    doc: dict[str, Any], title: str | None, version: str, ui_locale: str | None = None
) -> str:
    r = R(resolve_locale(ui_locale or doc.get("language")))
    title = title or r.t("cmp.title")
    lang = doc.get("language", "en")
    sides = doc["sides"]
    n = sides["left"]["coverage"]["denominator"]
    head = r.T(
        "ov.headline.compare",
        tag="p",
        cls="headline",
        sources={
            "i18n": "ov.sources",
            "p": {"n": len({o["locator"].get("source_id") for o in doc["obligations"]})},
        },
    )
    cov_line = r.T(
        "cmp.headline_cov",
        tag="p",
        cls="state",
        l=sides["left"]["coverage"]["covered"],
        r=sides["right"]["coverage"]["covered"],
        n=n,
    )
    cards = []
    for s in ("left", "right"):
        side = sides[s]
        cov = side["coverage"]
        disp_rows = [
            ("disposition", d, cov["breakdown"].get(d, 0), DISP_COLOR.get(d, "neutral"))
            for d in DISP_COLOR
            if cov["breakdown"].get(d)
        ]
        type_rows = [
            ("type", t, side["items"]["by_type"][t], TYPE_COLOR.get(t, "neutral"))
            for t in TYPE_COLOR
            if side["items"]["by_type"].get(t)
        ]
        unm = (
            " ".join(f'<span class="tag mono">{_e(k)}</span>' for k in side["unmatched_items"])
            or f'<span class="d">{r.T("common.none")}</span>'
        )
        uns = (
            " ".join(f'<span class="tag mono">{_e(k)}</span>' for k in side["unsupported"])
            or f'<span class="d">{r.T("common.none")}</span>'
        )
        struct = "".join(f'<li lang="en">{_e(x)}</li>' for x in side["structural_issues"])
        cards.append(
            f'<div class="panel side-card cmp-{s[0]}"><h4><span class="side-mark"></span>{r.T("cmp.side." + s)}</h4>'
            f'<span class="file">{_e(side["baseline"]["source_file"])} · {_e(side["baseline"]["format"])}</span>'
            f'<div class="metrics">{_metric(r, r.T("m.full_cov"), _frac(cov["covered"], n), r.T("m.denominator", what={"i18n": "m.den.inventory"}), "m.full_cov.d")}'
            f"{_metric(r, r.T('m.items'), str(side['items']['total']), r.T('m.criteria') + ': ' + str(side['criteria']))}</div>"
            f"<div><h4>{r.T('cmp.coverage')}</h4>{_legend_bar(r, disp_rows, n)}</div>"
            f"<div><h4>{r.T('ov.composition')}</h4>{_legend_bar(r, type_rows, side['items']['total'])}</div>"
            f"<div><h4>{r.T('cmp.unmatched')}</h4><p>{unm}</p></div><div><h4>{r.T('cmp.unsupported')}</h4><p>{uns}</p></div>"
            + (
                f'<div><h4>{r.T("cmp.structural")}</h4><ul class="plain">{struct}</ul></div>'
                if struct
                else ""
            )
            + "</div>"
        )
    notes = "".join(f"<li>{r.T(k)}</li>" for k in ("cmp.note.gold", "cmp.note.counts", "cmp.note.gates"))
    overview = _view(
        "overview",
        r,
        "cmp.title",
        "cmp.d",
        f'{head}{cov_line}<div class="sides">{"".join(cards)}</div>'
        f'<section class="block"><h3>{r.T("cmp.notes")}</h3><div class="panel"><ul class="plain">{notes}</ul></div></section>',
    )
    rows = "".join(
        f'<tr data-row data-agree="{_e(o["agreement"])}" class="{"differs" if o["agreement"] == "differs" else ""}" id="ob-{_e(o["key"])}">'
        f'<td class="mono">{_e(o["key"])}</td><td><span lang="{_e(lang)}">{_e(o["text"])}</span><br><span class="quote">{_e(o["quote"])}</span>'
        f'<br><span class="loc">{_e(o["locator"].get("member"))}:{_e(o["locator"].get("line_start"))}</span></td>'
        f'<td>{r.pill("disposition", o["left"]["disposition"])}<br><span class="mono">{_e(", ".join(o["left"].get("covered_by", [])))}</span></td>'
        f'<td>{r.pill("disposition", o["right"]["disposition"])}<br><span class="mono">{_e(", ".join(o["right"].get("covered_by", [])))}</span></td>'
        f"<td>{r.T('cmp.same') if o['agreement'] == 'same' else r.T('cmp.differs')}</td></tr>"
        for o in doc["obligations"]
    )
    alignment = _view(
        "alignment",
        r,
        "cmp.alignment",
        "rq.obligations.d",
        f'<div class="panel"><div class="toolbar">{_filter_select(r, "al-table", "agree", "cmp.filter.agreement", [("same", r.T("cmp.same")), ("differs", r.T("cmp.differs"))], "al-agree")}'
        f'<span class="d"><span id="al-table-n">{len(doc["obligations"])}</span>/{len(doc["obligations"])}</span></div>'
        f'<div class="tablewrap"><table class="grid" id="al-table"><thead><tr><th>{r.T("col.key")}</th><th>{r.T("col.obligation")}</th>'
        f"<th>{r.T('cmp.side.left')}</th><th>{r.T('cmp.side.right')}</th><th>{r.T('col.agreement')}</th></tr></thead><tbody>{rows}</tbody></table></div></div>",
    )
    mrows = "".join(
        f'<tr data-row data-rel="{_e(m["relation"])}"><td class="mono">{_e(", ".join(m["left"]))}</td><td>{r.pill("cmp_relation", m["relation"])}<br><span class="mono">{_e(m["cardinality"])}</span></td>'
        f'<td class="mono">{_e(", ".join(m["right"]))}</td><td lang="{_e(lang)}">{_e(m["rationale"])}'
        + (
            f"<ul>{''.join(f'<li>{_e(x)}</li>' for x in m.get('differences', []))}</ul>"
            if m.get("differences")
            else ""
        )
        + "</td></tr>"
        for m in doc["mappings"]
    )
    rels = sorted({m["relation"] for m in doc["mappings"]})
    card = ", ".join(f"{k}: {v}" for k, v in doc["mapping_cardinality"].items())
    mappings = _view(
        "mappings",
        r,
        "cmp.mappings",
        "cmp.mappings.d",
        f'<div class="panel"><div class="toolbar">{_filter_select(r, "mp-table", "rel", "col.relation", [(x, _e(r.t.enum("cmp_relation", x))) for x in rels], "mp-rel")}'
        f'<span class="d">{r.T("col.cardinality")}: <span class="mono">{_e(card)}</span></span></div>'
        f'<div class="tablewrap"><table class="grid" id="mp-table"><thead><tr><th>{r.T("cmp.side.left")}</th><th>{r.T("col.relation")}</th>'
        f"<th>{r.T('cmp.side.right')}</th><th>{r.T('col.rationale')}</th></tr></thead><tbody>{mrows}</tbody></table></div></div>",
    )
    fs = sorted(doc["findings"], key=lambda f: SEV_ORDER.index(f["severity"]))
    fcards = "".join(
        _finding_card(
            r,
            {**f, "id": f"cmp-{i}"},
            lang,
            " ".join(f'<span class="tag mono">{_e(a)}</span>' for a in f["affects"]),
            f.get("side", ""),
        )
        for i, f in enumerate(fs)
    )
    findings = _view(
        "findings",
        r,
        "fd.title",
        None,
        f'<div class="cards" id="fd-cards">{fcards}</div>'
        if fs
        else f'<div class="panel empty">{r.T("fd.none")}</div>',
    )
    data = _data(r, doc, "canonical", "comparison.json", "actions.download_cmp")
    entries = [
        ("overview", "nav.overview", "home", None),
        ("alignment", "cmp.alignment", "target", len(doc["obligations"])),
        ("mappings", "cmp.mappings", "compare", len(doc["mappings"])),
        ("findings", "fd.title", "flag", len(fs)),
        ("data", "nav.data", "code", None),
    ]
    subtitle = f"{r.T('header.run')} <code>{_e(doc['run_id'])}</code>"
    return _page(
        r,
        title=title,
        mode="compare",
        subtitle=subtitle,
        content_lang=lang,
        nav=_nav(r, entries),
        views=overview + alignment + mappings + findings + data,
        version=version,
        synthetic=False,
    )


def criteria_preview(crits: list[dict[str, Any]], style: str, language: str) -> str:
    """Native rendering of a work item's criteria (as written to the tracker field)."""
    return sanitize_html(criteria_html(crits, style, language))
