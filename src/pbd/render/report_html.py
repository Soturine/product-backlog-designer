"""Offline, two-layer HTML report rendered deterministically from canonical artifacts.

Layer 1 (executive) answers what was reviewed, what is sound, what differs, what needs a decision
and what is not proven. Layer 2 (technical) exposes every source, claim, work item, field,
criterion, task, relation, finding, question, gate and limitation. All content is rendered on the
server side; JavaScript only adds search, filters, expand/collapse and theme switching. No
external resources; a Content-Security-Policy allows only the embedded script by hash.

Design tokens (light/dark palettes, radii, fonts and the status-tone system) are adopted from
Assertiva ``assertiva/report_html.py`` (Apache-2.0, commit d4d8d492); see ATTRIBUTION.md.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
from collections import Counter
from typing import Any

from pbd.render.exports import criteria_by_parent, tree_order
from pbd.render.richtext import criteria_html, criterion_sentence, strip_html
from pbd.render.sanitize import sanitize_html

UI = {
    "pt": {
        "summary": "Resumo executivo",
        "backlog": "Backlog",
        "requirements": "Requisitos",
        "findings": "Achados",
        "questions": "Perguntas",
        "gates": "Gates de qualidade",
        "sources": "Fontes",
        "azure": "Pacote Azure",
        "data": "Dados",
        "limitations": "Limitações",
        "search": "Buscar por ID, título, critério ou texto",
        "all_types": "Todos os tipos",
        "all_verdicts": "Todas as avaliações",
        "expand": "Expandir tudo",
        "collapse": "Recolher tudo",
        "shown": "itens visíveis",
        "reviewed": "O que foi analisado",
        "sound": "O que está consistente",
        "differs": "O que diverge",
        "decide": "O que precisa de decisão",
        "unproven": "O que não está comprovado",
        "items": "Work Items",
        "criteria": "Critérios de aceite",
        "coverage": "Cobertura independente",
        "read": "Membros lidos",
        "open_q": "Perguntas abertas",
        "description": "Descrição",
        "acceptance": "Critérios de aceite",
        "fields": "Campos",
        "trace": "Rastreabilidade",
        "review": "Revisão independente",
        "none": "Nenhum.",
        "synthetic": "SINTÉTICO",
        "not_published": "Não publicado: pacote e plano são locais.",
        "theme": "Alternar tema",
        "obligations": "Obrigações do inventário independente",
        "claims": "Claims reconciliadas",
        "expected": "Esperado",
        "actual": "Atual",
        "why": "Por quê",
        "impact": "Impacto",
        "recommendation": "Recomendação",
        "status": "Status",
        "reason": "Motivo",
        "verification": "Verificação",
        "denominator": "Denominador",
        "members": "Membros",
        "native": "Campos nativos",
        "proposed": "Proposto (não escrito)",
        "canonical": "JSON canônico completo",
        "privacy": "Conteúdo potencialmente sensível: compartilhe somente com quem pode ver as fontes.",
        "dependencies": "Dependências",
        "no_results": "Nenhum item corresponde à busca.",
        "run": "Execução",
    },
    "en": {
        "summary": "Executive summary",
        "backlog": "Backlog",
        "requirements": "Requirements",
        "findings": "Findings",
        "questions": "Questions",
        "gates": "Quality gates",
        "sources": "Sources",
        "azure": "Azure package",
        "data": "Data",
        "limitations": "Limitations",
        "search": "Search by ID, title, criterion or text",
        "all_types": "All types",
        "all_verdicts": "All verdicts",
        "expand": "Expand all",
        "collapse": "Collapse all",
        "shown": "items shown",
        "reviewed": "What was reviewed",
        "sound": "What is sound",
        "differs": "What differs",
        "decide": "What needs a decision",
        "unproven": "What is not proven",
        "items": "Work items",
        "criteria": "Acceptance criteria",
        "coverage": "Independent coverage",
        "read": "Members read",
        "open_q": "Open questions",
        "description": "Description",
        "acceptance": "Acceptance criteria",
        "fields": "Fields",
        "trace": "Traceability",
        "review": "Independent review",
        "none": "None.",
        "synthetic": "SYNTHETIC",
        "not_published": "Not published: package and plan are local only.",
        "theme": "Toggle theme",
        "obligations": "Independent inventory obligations",
        "claims": "Reconciled claims",
        "expected": "Expected",
        "actual": "Actual",
        "why": "Why",
        "impact": "Impact",
        "recommendation": "Recommendation",
        "status": "Status",
        "reason": "Reason",
        "verification": "Verification",
        "denominator": "Denominator",
        "members": "Members",
        "native": "Native fields",
        "proposed": "Proposed (not written)",
        "canonical": "Full canonical JSON",
        "privacy": "Potentially sensitive content: share only with people allowed to see the sources.",
        "dependencies": "Dependencies",
        "no_results": "No item matches the search.",
        "run": "Run",
    },
}

CSS_TOKENS = """:root{color-scheme:light;
--bg:#f3f5fa;--side:#ffffff;--surface:#ffffff;--surface-2:#f7f8fc;--sunk:#eef1f7;--rule:#e2e6ef;--rule-strong:#ccd3e0;
--ink:#0f172a;--ink-2:#334155;--muted:#5b6578;--faint:#8a93a6;
--accent:#3b5bdb;--accent-2:#6d4aff;--accent-soft:#e9edff;--on-tone:#ffffff;--logo-a:#4f6bff;--logo-b:#7b4dff;
--pass:#15803d;--fail:#c02626;--warn:#b45309;--unknown:#5f6b7f;--info:#1d63c9;
--glow:rgba(59,91,219,.07);--shadow:0 1px 2px rgba(15,23,42,.05);--lift:0 10px 30px -18px rgba(15,23,42,.35);
--r-sm:7px;--r:12px;--r-lg:16px;
--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI Variable Text","Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,"SF Mono","Cascadia Mono",Menlo,Consolas,"Liberation Mono",monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#080d1a;--side:#0a1020;--surface:#0e1628;--surface-2:#111b31;--sunk:#0b1324;--rule:rgba(148,163,184,.13);--rule-strong:rgba(148,163,184,.24);
--ink:#e9eef8;--ink-2:#c4ccdc;--muted:#8f9ab0;--faint:#68738a;
--accent:#7b93ff;--accent-2:#9b7bff;--accent-soft:rgba(91,124,250,.16);--on-tone:#08101f;--logo-a:#4f6bff;--logo-b:#8a5cff;
--pass:#3ddc97;--fail:#ff7b7b;--warn:#f6b44b;--unknown:#a3adbf;--info:#6cb2ff;
--glow:rgba(91,124,250,.20);--shadow:0 1px 2px rgba(0,0,0,.4);--lift:0 18px 40px -22px rgba(0,0,0,.9)}}
:root[data-theme="dark"]{color-scheme:dark;
--bg:#080d1a;--side:#0a1020;--surface:#0e1628;--surface-2:#111b31;--sunk:#0b1324;--rule:rgba(148,163,184,.13);--rule-strong:rgba(148,163,184,.24);
--ink:#e9eef8;--ink-2:#c4ccdc;--muted:#8f9ab0;--faint:#68738a;
--accent:#7b93ff;--accent-2:#9b7bff;--accent-soft:rgba(91,124,250,.16);--on-tone:#08101f;--logo-a:#4f6bff;--logo-b:#8a5cff;
--pass:#3ddc97;--fail:#ff7b7b;--warn:#f6b44b;--unknown:#a3adbf;--info:#6cb2ff;
--glow:rgba(91,124,250,.20);--shadow:0 1px 2px rgba(0,0,0,.4);--lift:0 18px 40px -22px rgba(0,0,0,.9)}
.tone-pass{--tone:var(--pass)}.tone-fail{--tone:var(--fail)}.tone-warn{--tone:var(--warn)}.tone-blocked{--tone:var(--warn)}
.tone-unknown{--tone:var(--unknown)}.tone-not_run{--tone:var(--faint)}.tone-neutral{--tone:var(--muted)}.tone-accent{--tone:var(--accent)}
.tone-info{--tone:var(--info)}.tone-muted{--tone:var(--faint)}
"""

CSS_COMPONENTS = """*,*::before,*::after{box-sizing:border-box}
html{scroll-padding-top:120px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-underline-offset:3px}code,pre{font-family:var(--mono);font-size:.84em}
code{overflow-wrap:anywhere}:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:5px}
.skip{position:absolute;left:16px;top:-60px;background:var(--surface);padding:8px 14px;border-radius:var(--r-sm);z-index:40}
.skip:focus{top:10px}[hidden]{display:none!important}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
header.top{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--surface) 92%,transparent);
backdrop-filter:blur(8px);border-bottom:1px solid var(--rule)}
.bar{max-width:1240px;margin:0 auto;padding:12px 20px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.logo{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,var(--logo-a),var(--logo-b));flex:none}
.brand h1{font-size:1.05rem;margin:0}.brand p{margin:0;color:var(--muted);font-size:.8rem}
.badge{display:inline-flex;align-items:center;gap:6px;padding:2px 9px;border-radius:999px;font-size:.75rem;
font-weight:600;border:1px solid color-mix(in srgb,var(--tone,var(--muted)) 40%,var(--rule));
color:var(--tone,var(--muted));background:color-mix(in srgb,var(--tone,var(--muted)) 9%,transparent)}
.spacer{flex:1}button,select,input{font:inherit;color:inherit}
.btn{border:1px solid var(--rule-strong);background:var(--surface);border-radius:var(--r-sm);padding:6px 12px;cursor:pointer}
.btn:hover{border-color:var(--accent)}
nav.tabs{max-width:1240px;margin:0 auto;padding:0 20px 8px;display:flex;gap:4px;overflow-x:auto}
nav.tabs a{padding:6px 12px;border-radius:999px;color:var(--ink-2);text-decoration:none;white-space:nowrap;font-size:.88rem}
nav.tabs a:hover{background:var(--accent-soft);color:var(--accent)}
main{max-width:1240px;margin:0 auto;padding:20px}
section{margin:0 0 28px}h2{font-size:1.25rem;margin:0 0 12px}h3{font-size:1rem;margin:14px 0 8px}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);padding:16px;box-shadow:var(--shadow)}
.verdict{border-left:4px solid var(--tone);display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:14px 0}
.kpi .v{font-size:1.6rem;font-weight:700}.kpi .l{color:var(--muted);font-size:.82rem}
.kpi .d{color:var(--faint);font-size:.78rem}
.layer1{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.layer1 ul{margin:6px 0 0;padding-left:18px}.layer1 li{margin:3px 0}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 12px;position:sticky;top:96px;z-index:10;
background:var(--bg);padding:8px 0}
.toolbar input[type=search]{flex:1 1 280px;min-width:200px;padding:8px 12px;border:1px solid var(--rule-strong);
border-radius:var(--r-sm);background:var(--surface)}
.toolbar select{padding:7px 10px;border:1px solid var(--rule-strong);border-radius:var(--r-sm);background:var(--surface)}
details.wi{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);margin:8px 0;
border-left:4px solid var(--tone,var(--rule-strong))}
details.wi>summary{list-style:none;cursor:pointer;padding:10px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
details.wi>summary::-webkit-details-marker{display:none}
details.wi>summary::before{content:"\\25B8";color:var(--muted);transition:transform .15s}
details.wi[open]>summary::before{transform:rotate(90deg)}
.wi .body{padding:0 16px 14px 34px}.wi .children{margin-left:14px}
.t-epic{--tone:#7b4dff}.t-feature{--tone:var(--info)}.t-story,.t-enabler,.t-spike,.t-bug{--tone:var(--pass)}
.t-task{--tone:var(--warn)}.title{font-weight:600}.mono{font-family:var(--mono);font-size:.78rem;color:var(--muted)}
.rich p{margin:4px 0}.rich ul{margin:4px 0;padding-left:20px}
table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{border:1px solid var(--rule);padding:6px 8px;
text-align:left;vertical-align:top}th{background:var(--surface-2)}
.tablewrap{overflow-x:auto}.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.finding{border-left:4px solid var(--tone)}.sev-critical,.sev-high{--tone:var(--fail)}.sev-medium{--tone:var(--warn)}
.sev-low,.sev-info{--tone:var(--info)}dl.kv{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;margin:6px 0}
dl.kv dt{color:var(--muted)}dl.kv dd{margin:0}.quote{color:var(--ink-2);font-style:italic}
pre.json{max-height:480px;overflow:auto;background:var(--sunk);padding:12px;border-radius:var(--r-sm)}
.notice{color:var(--muted);font-size:.85rem}
@media (max-width:640px){.bar{padding:10px 12px}main{padding:12px}.wi .body{padding-left:14px}
.toolbar{top:86px}dl.kv{grid-template-columns:1fr}}
@media print{header.top,.toolbar,nav.tabs{position:static}details.wi{break-inside:avoid}.btn{display:none}}
"""

JS = """(function(){
var d=document,root=d.documentElement,KEY='pbd-theme';
try{var s=localStorage.getItem(KEY);if(s)root.setAttribute('data-theme',s);}catch(e){}
var tb=d.getElementById('theme');if(tb)tb.addEventListener('click',function(){
var dark=root.getAttribute('data-theme')==='dark'||(!root.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);
var next=dark?'light':'dark';root.setAttribute('data-theme',next);try{localStorage.setItem(KEY,next);}catch(e){}});
function norm(t){return (t||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();}
var items=[].slice.call(d.querySelectorAll('details.wi'));
items.forEach(function(el){el._t=norm(el.getAttribute('data-text'));});
var q=d.getElementById('q'),ft=d.getElementById('ftype'),fv=d.getElementById('fverdict'),out=d.getElementById('count'),
none=d.getElementById('noresults');
function apply(){var term=norm(q.value.trim()),type=ft.value,ver=fv.value,shown=0;
items.forEach(function(el){el._m=(!term||el._t.indexOf(term)>=0)&&(!type||el.getAttribute('data-type')===type)&&
(!ver||el.getAttribute('data-verdict')===ver);});
items.slice().reverse().forEach(function(el){var keep=el._m||[].some.call(el.querySelectorAll('details.wi'),function(c){return c._m;});
el.hidden=!keep;if(keep&&el._m)shown++;if(keep&&(term||type||ver)&&!el._m)el.open=true;});
out.textContent=shown;none.hidden=shown>0;}
[q,ft,fv].forEach(function(e){e.addEventListener('input',apply);});
d.getElementById('expand').addEventListener('click',function(){items.forEach(function(e){e.open=true;});});
d.getElementById('collapse').addEventListener('click',function(){items.forEach(function(e){e.open=false;});});
apply();})();"""


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _tone(status: str) -> str:
    return {
        "PASS": "pass",
        "FAIL": "fail",
        "BLOCKED": "blocked",
        "NOT_RUN": "not_run",
        "NOT_APPLICABLE": "muted",
        "pass": "pass",
        "concern": "warn",
        "fail": "fail",
        "COVERED": "pass",
        "PARTIALLY_COVERED": "warn",
        "NOT_COVERED": "fail",
        "QUESTION_REQUIRED": "info",
        "CONFLICTING": "fail",
        "BLOCKED_OB": "warn",
        "OUT_OF_SCOPE": "muted",
        "SUPERSEDED": "muted",
        "DEFERRED": "muted",
    }.get(status, "neutral")


def _badge(text: str, tone: str) -> str:
    return f'<span class="badge tone-{tone}">{_e(text)}</span>'


def _list(values: list[str], empty: str) -> str:
    if not values:
        return f'<p class="notice">{_e(empty)}</p>'
    return "<ul>" + "".join(f"<li>{v}</li>" for v in values) + "</ul>"


def render_report(ctx: dict[str, Any]) -> str:
    backlog: dict[str, Any] = ctx["backlog"]
    keys: dict[str, str] = ctx["keys"]
    review: dict[str, Any] = ctx["review"]
    gates: dict[str, Any] = ctx["gates"]
    metrics: dict[str, Any] = ctx["metrics"]
    lang = "pt" if backlog["language"].lower().startswith("pt") else "en"
    t = UI[lang]
    claims = {c["id"]: c for c in backlog["claims"]}
    rev_items = {e["key"]: e for e in review.get("items", [])}
    rev_crits = {e["key"]: e for e in review.get("criteria", [])}
    by_parent = criteria_by_parent(backlog)
    gate_rows = gates["gates"]
    gcount = Counter(g["status"] for g in gate_rows)
    title = ctx.get("title") or "Product Backlog"

    # ------------------------------------------------------------ layer 1
    worst = "fail" if gcount["FAIL"] else ("blocked" if gcount["BLOCKED"] else "pass")
    verdict_text = {
        "fail": f"{gcount['FAIL']} gate(s) FAIL · {gcount['BLOCKED']} BLOCKED · {gcount['NOT_RUN']} NOT_RUN",
        "blocked": f"{gcount['BLOCKED']} gate(s) BLOCKED · {gcount['NOT_RUN']} NOT_RUN",
        "pass": f"{gcount['PASS']} gate(s) PASS · {gcount['NOT_RUN']} NOT_RUN",
    }[worst]
    cov = metrics["coverage"]
    kpis = [
        (
            t["items"],
            metrics["items"]["total"],
            ", ".join(f"{k}: {v}" for k, v in metrics["items"]["by_type"].items()),
        ),
        (t["criteria"], metrics["criteria"]["total"], f"{metrics['criteria']['proposed']} proposed"),
        (t["coverage"], f"{cov['covered']}/{cov['total']}", f"provenance: {cov['provenance']}"),
        (
            t["read"],
            f"{metrics['sources']['members_read']}/{metrics['sources']['members_total']}",
            f"{metrics['sources']['sources']} source(s)",
        ),
        (
            t["findings"],
            metrics["findings"]["total"],
            ", ".join(f"{k}: {v}" for k, v in metrics["findings"]["by_severity"].items()),
        ),
        (t["open_q"], metrics["questions"]["open"], f"{metrics['questions']['blocking']} blocking"),
    ]
    kpi_html = "".join(
        f'<div class="card kpi"><div class="v">{_e(v)}</div><div class="l">{_e(label)}</div>'
        f'<div class="d">{_e(detail)}</div></div>'
        for label, v, detail in kpis
    )
    reviewed = [
        f"{_e(s['selector'])} — {_e(s['authority'])} ({_e(s['read_status'])})" for s in backlog["sources"]
    ]
    sound = [f"{_e(g['id'])} {_e(g['scope'])}" for g in gate_rows if g["status"] == "PASS"]
    differs = [
        f"{_badge(f['severity'], _tone_sev(f['severity']))} {_e(f.get('actual') or f['why'])}"
        for f in backlog["findings"]
    ] + [f"{_e(g['id'])}: {_e(g['reason'])}" for g in gate_rows if g["status"] == "FAIL"]
    decide = [_e(q["text"]) for q in backlog["questions"] if q["status"] == "open"]
    unproven = [
        f"{_e(g['id'])} {_e(g['status'])}: {_e(g['reason'])}"
        for g in gate_rows
        if g["status"] in ("BLOCKED", "NOT_RUN")
    ] + [_e(x) for x in ctx.get("limitations", [])]
    layer1 = "".join(
        f'<div class="card"><h3>{_e(h)}</h3>{_list(v, t["none"])}</div>'
        for h, v in (
            (t["reviewed"], reviewed),
            (t["sound"], sound),
            (t["differs"], differs),
            (t["decide"], decide),
            (t["unproven"], unproven),
        )
    )

    # ------------------------------------------------------------ layer 2: tree
    tree = tree_order(backlog)
    children: dict[str | None, list[dict[str, Any]]] = {}
    for item in tree:
        children.setdefault(item["parent"], []).append(item)

    def trace_html(refs: list[str]) -> str:
        rows = []
        for ref in refs:
            c = claims.get(ref)
            if not c:
                continue
            for ev in c["evidence"]:
                loc = ev.get("locator", {})
                rows.append(
                    f"<li><code>{_e(keys.get(ref, ref))}</code> {_e(c['text'])} — "
                    f"<span class='mono'>{_e(loc.get('member'))}:{_e(loc.get('line_start'))}"
                    f"{'' if loc.get('line_end') in (None, loc.get('line_start')) else '-' + _e(loc.get('line_end'))}"
                    f"</span> <span class='quote'>“{_e(ev.get('summary', ''))}”</span></li>"
                )
        return "<ul>" + "".join(rows) + "</ul>" if rows else ""

    def item_html(item: dict[str, Any]) -> str:
        key = keys.get(item["id"], item["id"])
        rev = rev_items.get(key, {})
        crits = by_parent.get(item["id"], [])
        desc = sanitize_html(item.get("description", {}).get("value", ""))
        text = " ".join(
            [item["id"], key, item["title"], strip_html(desc)]
            + [c["visible_id"] + " " + criterion_sentence(c) for c in crits]
        )
        parts = [
            f"<summary>{_badge(item['type'], 'accent')}<span class='mono'>{_e(key)}</span>"
            f"<span class='title'>{_e(item['title'])}</span>"
            + (_badge(rev["verdict"], _tone(rev["verdict"])) if rev.get("verdict") else "")
            + (f"<span class='mono'>{len(crits)} AC</span>" if crits else "")
            + "</summary><div class='body'>"
        ]
        parts.append(f"<p class='mono'>{_e(item['id'])}</p>")
        if desc:
            parts.append(f"<h3>{_e(t['description'])}</h3><div class='rich'>{desc}</div>")
        if crits:
            parts.append(
                f"<h3>{_e(t['acceptance'])}</h3><div class='rich tablewrap'>"
                f"{sanitize_html(criteria_html(crits, item.get('acceptance_style', 'list'), backlog['language']))}"
                "</div>"
            )
            crit_rows = "".join(
                f"<tr><td>{_e(c['visible_id'])}</td><td>{_e(c['status'])}</td><td>"
                f"{_badge(rev_crits.get(keys.get(c['id'], ''), {}).get('verdict', '—'), _tone(rev_crits.get(keys.get(c['id'], ''), {}).get('verdict', '')))}"
                f"</td><td>{_e(rev_crits.get(keys.get(c['id'], ''), {}).get('notes', ''))}</td><td>"
                f"{', '.join(_e(keys.get(r, r)) for r in c['claim_refs']) or _e(c.get('rationale', ''))}</td></tr>"
                for c in crits
            )
            parts.append(
                "<div class='tablewrap'><table><thead><tr><th>ID</th><th>status</th><th>review</th>"
                f"<th>notes</th><th>claims</th></tr></thead><tbody>{crit_rows}</tbody></table></div>"
            )
        if item.get("fields"):
            frows = "".join(
                f"<tr><td>{_e(n)}</td><td>{_e(v.get('value', '—'))}</td><td>{_badge(v['state'], 'info')}"
                f"</td><td>{_e(v.get('rationale', ''))}</td></tr>"
                for n, v in sorted(item["fields"].items())
            )
            parts.append(
                f"<h3>{_e(t['fields'])}</h3><div class='tablewrap'><table><tbody>{frows}</tbody></table></div>"
            )
        tr = trace_html(item.get("claim_refs", []))
        if tr or item.get("technical_rationale"):
            parts.append(
                f"<h3>{_e(t['trace'])}</h3>{tr}"
                + (
                    f"<p><em>{_e(item.get('technical_rationale'))}</em></p>"
                    if item.get("technical_rationale")
                    else ""
                )
            )
        if rev:
            inv = rev.get("invest") or {}
            inv_rows = "".join(
                f"<tr><td>{_e(dim)}</td><td>{_badge(v.get('rating', '—'), 'neutral')}</td>"
                f"<td>{_e(v.get('note', ''))}</td></tr>"
                for dim, v in inv.items()
                if isinstance(v, dict)
            )
            parts.append(
                f"<h3>{_e(t['review'])}</h3><dl class='kv'><dt>verdict</dt><dd>{_e(rev.get('verdict'))}</dd>"
                f"<dt>source</dt><dd>{_e(rev.get('source_support'))}</dd>"
                + (
                    f"<dt>tasks</dt><dd>{_e(rev.get('task_sufficiency'))}</dd>"
                    if rev.get("task_sufficiency")
                    else ""
                )
                + f"<dt>notes</dt><dd>{_e(rev.get('notes', ''))}</dd></dl>"
                + (
                    f"<div class='tablewrap'><table><tbody>{inv_rows}</tbody></table></div>"
                    if inv_rows
                    else ""
                )
            )
        kids = children.get(item["id"], [])
        if kids:
            parts.append("<div class='children'>" + "".join(item_html(k) for k in kids) + "</div>")
        parts.append("</div>")
        return (
            f"<details class='wi t-{_e(item['type'])}' id='{_e(item['id'])}' data-type='{_e(item['type'])}' "
            f"data-verdict='{_e(rev.get('verdict', ''))}' data-text='{_e(text)}'>"
            + "".join(parts)
            + "</details>"
        )

    roots = children.get(None, [])
    tree_html = "".join(item_html(i) for i in roots)
    types = sorted({i["type"] for i in backlog["items"]})
    type_opts = "".join(f"<option value='{_e(x)}'>{_e(x)}</option>" for x in types)

    # ------------------------------------------------------------ other technical views
    claim_rows = "".join(
        f"<tr><td><code>{_e(keys.get(c['id'], c['id']))}</code></td><td>{_e(c['text'])}</td><td>{_e(c['category'])}</td>"
        f"<td>{_badge(c['disposition']['status'], _tone(c['disposition']['status']))}</td>"
        f"<td>{', '.join(_e(keys.get(x, x)) for x in c['disposition'].get('covered_by', []))}</td>"
        f"<td>{_e(c['disposition'].get('rationale', ''))}</td></tr>"
        for c in backlog["claims"]
    )
    ob_rows = "".join(
        f"<tr><td><code>{_e(o['key'])}</code></td><td>{_e(o.get('text', ''))}</td>"
        f"<td class='mono'>{_e(o['locator'].get('member'))}:{_e(o['locator'].get('line_start'))}</td>"
        f"<td>{_badge(o['disposition'], _tone(o['disposition']))}</td>"
        f"<td>{', '.join(_e(k) for k in o.get('covered_by', []))}</td><td>{_e(o.get('rationale', ''))}</td></tr>"
        for o in review.get("independent_obligations", [])
    )
    finding_html = (
        "".join(
            f"<div class='card finding sev-{_e(f['severity'])}'><p>{_badge(f['severity'], _tone_sev(f['severity']))} "
            f"{_badge(f['classification'], 'neutral')} {_badge(f.get('gate', ''), 'muted') if f.get('gate') else ''}</p>"
            f"<dl class='kv'><dt>{_e(t['expected'])}</dt><dd>{_e(f['expected'])}</dd><dt>{_e(t['actual'])}</dt>"
            f"<dd>{_e(f['actual'])}</dd><dt>{_e(t['why'])}</dt><dd>{_e(f['why'])}</dd><dt>{_e(t['impact'])}</dt>"
            f"<dd>{_e(f['impact'])}</dd><dt>{_e(t['recommendation'])}</dt><dd>{_e(f['recommendation'])}</dd>"
            f"<dt>IDs</dt><dd>{', '.join(_e(keys.get(a, a)) for a in f['affects'])}</dd></dl></div>"
            for f in backlog["findings"]
        )
        or f"<p class='notice'>{_e(t['none'])}</p>"
    )
    question_html = _list(
        [
            f"{_e(q['text'])} — <em>{_e(q['impact'])}</em>"
            + (" " + _badge("blocking", "fail") if q["blocking"] else "")
            + (f" ({', '.join(_e(keys.get(a, a)) for a in q['affects'])})" if q["affects"] else "")
            for q in backlog["questions"]
        ],
        t["none"],
    )
    gate_html = "".join(
        f"<tr><td><code>{_e(g['id'])}</code> {_e(g['scope'])}</td><td>{_badge(g['status'], _tone(g['status']))}</td>"
        f"<td>{_e(g.get('verification', '—'))}</td><td>{_e(g['reason'])}</td><td>"
        + (
            _e(
                f"{g['denominator']['examined']}/{g['denominator']['total']} ({g['denominator']['provenance']})"
            )
            if g.get("denominator")
            else "—"
        )
        + "</td></tr>"
        for g in gate_rows
    )
    src_html = "".join(
        f"<div class='card'><h3>{_e(s['selector'])} {_badge(s['authority'], 'accent')} "
        f"{_badge(s['read_status'], 'pass' if s['read_status'] == 'complete' else 'warn')}</h3>"
        f"<p class='mono'>{_e(s['id'])} · {_e(s['digest'])}</p><ul>"
        + "".join(
            f"<li>{_e(m['path'])} — {_e(m['status'])}{(' · ' + _e(m['reason'])) if m.get('reason') else ''}</li>"
            for m in s.get("members", [])
        )
        + "</ul></div>"
        for s in backlog["sources"]
    )
    rel_items = {i["id"]: i for i in backlog["items"]}
    dep_html = _list(
        [
            f"{_e(keys.get(r['source'], r['source']))} → {_e(r['type'])} → "
            f"{_e(keys.get(r['target'], r['target']) if isinstance(r['target'], str) else r['target'])}: "
            f"{_e(r['reason'])} ({_e(r['status'])})"
            for r in backlog["relations"]
            if r["source"] in rel_items
        ],
        t["none"],
    )
    azure = ctx.get("azure")
    azure_html = ""
    if azure:
        rows = "".join(
            f"<details class='card'><summary><code>{_e(keys.get(w['pbd_id'], w['pbd_id']))}</code> "
            f"{_e(w['work_item_type'])}</summary><div class='tablewrap'><table><tbody>"
            + "".join(
                f"<tr><th>{_e(k)}</th><td><div class='rich'>{sanitize_html(str(v))}</div></td></tr>"
                for k, v in w["fields"].items()
            )
            + "".join(
                f"<tr><th>{_e(k)}</th><td>{_badge(t['proposed'], 'warn')} {_e(v['value'])}</td></tr>"
                for k, v in w.get("proposed_fields_not_written", {}).items()
            )
            + "</tbody></table></div></details>"
            for w in azure["work_items"]
        )
        azure_html = (
            f"<section id='azure'><h2>{_e(t['azure'])}</h2><p class='notice'>{_e(azure['note'])} "
            f"profile: {_e(azure['profile'])} (verified: {_e(azure['profile_verified'])})</p>{rows}"
            f"{_list([_e(x) for x in azure['limitations']], t['none'])}</section>"
        )
    canonical = json.dumps(backlog, ensure_ascii=False, indent=1, sort_keys=True)

    script_hash = base64.b64encode(hashlib.sha256(JS.encode("utf-8")).digest()).decode("ascii")
    csp = (
        f"default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; img-src data:; "
        "base-uri 'none'; form-action 'none'"
    )
    synth = _badge(t["synthetic"], "warn") if backlog.get("synthetic") else ""
    nav = "".join(
        f"<a href='#{a}'>{_e(t[k])}</a>"
        for a, k in (
            ("summary", "summary"),
            ("backlog", "backlog"),
            ("requirements", "requirements"),
            ("findings", "findings"),
            ("questions", "questions"),
            ("gates", "gates"),
            ("sources", "sources"),
        )
    )
    nav += f"<a href='#azure'>{_e(t['azure'])}</a>" if azure else ""
    nav += f"<a href='#data'>{_e(t['data'])}</a>"
    return f"""<!DOCTYPE html>
<html lang="{_e(backlog["language"])}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{_e(csp)}">
<meta name="generator" content="pbd {_e(ctx.get("version", ""))}">
<title>{_e(title)} — PBD</title><style>{CSS_TOKENS}{CSS_COMPONENTS}</style></head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="bar"><div class="logo" aria-hidden="true"></div><div class="brand"><h1>{_e(title)}</h1>
<p>{_e(t["run"])} <code>{_e(backlog["run_id"])}</code> · {_e(backlog["language"])} · profile {_e(backlog.get("profile"))}</p></div>
{synth}{_badge(t["not_published"], "info")}<span class="spacer"></span>
<button class="btn" id="theme" type="button" aria-label="{_e(t["theme"])}">◐</button></div>
<nav class="tabs" aria-label="sections">{nav}</nav></header>
<main id="main">
<section id="summary" aria-labelledby="h-summary"><h2 id="h-summary">{_e(t["summary"])}</h2>
<div class="card verdict tone-{worst}">{_badge(worst.upper(), worst)}<div><strong>{_e(verdict_text)}</strong>
<p class="notice">{_e(t["privacy"])}</p></div></div>
<div class="kpis">{kpi_html}</div><div class="layer1">{layer1}</div></section>
<section id="backlog" aria-labelledby="h-backlog"><h2 id="h-backlog">{_e(t["backlog"])}</h2>
<div class="toolbar" role="search"><label class="sr-only" for="q">{_e(t["search"])}</label>
<input id="q" type="search" placeholder="{_e(t["search"])}" autocomplete="off">
<label class="sr-only" for="ftype">type</label><select id="ftype"><option value="">{_e(t["all_types"])}</option>{type_opts}</select>
<label class="sr-only" for="fverdict">verdict</label><select id="fverdict"><option value="">{_e(t["all_verdicts"])}</option>
<option value="pass">pass</option><option value="concern">concern</option><option value="fail">fail</option></select>
<button class="btn" id="expand" type="button">{_e(t["expand"])}</button><button class="btn" id="collapse" type="button">{_e(t["collapse"])}</button>
<span aria-live="polite"><strong id="count">{len(backlog["items"])}</strong> {_e(t["shown"])}</span></div>
<p id="noresults" class="notice" hidden>{_e(t["no_results"])}</p>
<div id="tree">{tree_html}</div>
<h3>{_e(t["dependencies"])}</h3>{dep_html}</section>
<section id="requirements"><h2>{_e(t["requirements"])}</h2><h3>{_e(t["claims"])}</h3><div class="tablewrap"><table>
<thead><tr><th>key</th><th>claim</th><th>category</th><th>{_e(t["status"])}</th><th>covered by</th><th>rationale</th></tr></thead>
<tbody>{claim_rows}</tbody></table></div><h3>{_e(t["obligations"])}</h3><div class="tablewrap"><table>
<thead><tr><th>key</th><th>obligation</th><th>locator</th><th>{_e(t["status"])}</th><th>covered by</th><th>rationale</th></tr></thead>
<tbody>{ob_rows}</tbody></table></div></section>
<section id="findings"><h2>{_e(t["findings"])}</h2><div class="grid2">{finding_html}</div></section>
<section id="questions"><h2>{_e(t["questions"])}</h2><div class="card">{question_html}</div></section>
<section id="gates"><h2>{_e(t["gates"])}</h2><div class="tablewrap"><table><thead><tr><th>gate</th><th>{_e(t["status"])}</th>
<th>{_e(t["verification"])}</th><th>{_e(t["reason"])}</th><th>{_e(t["denominator"])}</th></tr></thead><tbody>{gate_html}</tbody></table></div></section>
<section id="sources"><h2>{_e(t["sources"])}</h2><div class="grid2">{src_html}</div>
<h3>{_e(t["limitations"])}</h3>{_list([_e(x) for x in ctx.get("limitations", [])], t["none"])}</section>
{azure_html}
<section id="data"><h2>{_e(t["data"])}</h2><details class="card"><summary>{_e(t["canonical"])}</summary>
<pre class="json">{_e(canonical)}</pre></details></section>
</main><script>{JS}</script></body></html>
"""


def _tone_sev(severity: str) -> str:
    return {"critical": "fail", "high": "fail", "medium": "warn", "low": "info", "info": "info"}.get(
        severity, "neutral"
    )
