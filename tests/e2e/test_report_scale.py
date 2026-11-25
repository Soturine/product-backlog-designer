"""Report at realistic volume: 1,000 synthetic items, budgets measured on the baseline host.

Budgets (see docs/reporting.md#performance-budgets) are generous multiples of the measured
baseline so they catch regressions (accidental quadratic work, unbounded duplication), not noise.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pbd.render.report_html import render_report

pytestmark = pytest.mark.playwright
sync_api = pytest.importorskip("playwright.sync_api")

N_EPICS, FEATURES, STORIES, TASKS = 10, 5, 4, 4  # 10 + 50 + 200 + 800 = 1060 items
# measured baseline (1,060 items, Windows 11, Edge): ~5.6 MB, render ~0.2 s, load ~1.7 s, filter ~16 ms
BUDGET_BYTES = 7_000_000
BUDGET_RENDER_S = 3.0
BUDGET_LOAD_MS = 6000
BUDGET_FILTER_MS = 300


def _ctx() -> dict[str, Any]:
    items, crits, rev_items, rev_crits, keys = [], [], [], [], {}
    n = 0

    def add(itype: str, parent: str | None, title: str) -> str:
        nonlocal n
        n += 1
        pid = f"PBD-{itype.upper()[:4]}-{n:012d}"
        key = f"K{n}"
        keys[pid] = key
        items.append(
            {
                "id": pid,
                "type": itype,
                "title": title,
                "parent": parent,
                "claim_refs": [],
                "origin": "generated",
                "status": "reviewed",
                "description": {
                    "format": "html",
                    "value": f"<p>Descrição número {n} — ação</p>",
                    "language": "pt-BR",
                },
            }
        )
        rev_items.append(
            {
                "key": key,
                "verdict": "pass" if n % 7 else "concern",
                "source_support": "supported",
                "notes": "nota" if n % 7 == 0 else "",
            }
        )
        return pid

    for e in range(N_EPICS):
        ep = add("epic", None, f"Épico {e}")
        for f in range(FEATURES):
            fe = add("feature", ep, f"Funcionalidade {e}.{f}")
            for s in range(STORIES):
                st = add("story", fe, f"História {e}.{f}.{s} sobre reservas")
                for c in range(2):
                    cid = f"PBD-AC-{len(crits):012d}"
                    keys[cid] = f"{keys[st]}.AC{c}"
                    crits.append(
                        {
                            "id": cid,
                            "parent": st,
                            "visible_id": f"CA-{c + 1:02d}",
                            "order": c,
                            "style": "list",
                            "expected_outcomes": [f"resultado {c}"],
                            "text": f"critério {c}",
                            "claim_refs": [],
                            "origin": "generated",
                            "status": "proposed",
                            "rationale": "r",
                        }
                    )
                    rev_crits.append({"key": keys[cid], "verdict": "pass", "source_support": "supported"})
                for t in range(TASKS):
                    add("task", st, f"Tarefa {e}.{f}.{s}.{t} de verificação")
    backlog = {
        "run_id": "PBD-RUN-SCALE0000000",
        "language": "pt-BR",
        "profile": "generic",
        "synthetic": True,
        "sources": [],
        "claims": [],
        "items": items,
        "criteria": crits,
        "relations": [],
        "questions": [],
        "decisions": [],
        "findings": [],
    }
    gates = {
        "gates": [
            {
                "id": f"G{i:02d}",
                "scope": "x",
                "status": "PASS",
                "reason": "ok",
                "verification": "verified",
                "evidence": [],
            }
            for i in range(1, 19)
        ]
    }
    metrics = {
        "items": {"total": len(items), "by_type": {"epic": 10, "feature": 50, "story": 200, "task": 800}},
        "criteria": {"total": len(crits), "proposed": len(crits)},
        "coverage": {"covered": 0, "total": 0},
        "sources": {"sources": 0, "members_total": 0, "members_read": 0},
        "findings": {"total": 0, "by_severity": {}},
        "questions": {"open": 0, "blocking": 0},
    }
    return {
        "backlog": backlog,
        "keys": keys,
        "review": {"items": rev_items, "criteria": rev_crits, "independent_obligations": []},
        "gates": gates,
        "metrics": metrics,
        "title": "Escala",
        "limitations": [],
        "azure": None,
        "version": "test",
        "mode": "generate",
    }


@pytest.fixture(scope="module")
def big(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, float, int]]:
    started = time.perf_counter()
    html = render_report(_ctx())
    elapsed = time.perf_counter() - started
    path = tmp_path_factory.mktemp("scale") / "report.html"
    path.write_text(html, encoding="utf-8")
    yield path, elapsed, len(html.encode("utf-8"))


def test_render_size_and_time_within_budget(big: tuple[Path, float, int]) -> None:
    _, elapsed, size = big
    assert size < BUDGET_BYTES, size
    assert elapsed < BUDGET_RENDER_S, elapsed


def test_browser_load_search_and_selection_at_volume(big: tuple[Path, float, int]) -> None:
    path = big[0]
    with sync_api.sync_playwright() as pw:
        browser = None
        for channel in ("msedge", "chrome"):
            try:
                browser = pw.chromium.launch(channel=channel)
                break
            except Exception:
                continue
        if browser is None:
            pytest.skip("no system Edge/Chrome available")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        t0 = time.perf_counter()
        page.goto(path.as_uri() + "#backlog")
        page.wait_for_selector("#tree a.lbl")
        load_ms = (time.perf_counter() - t0) * 1000
        assert load_ms < BUDGET_LOAD_MS, load_ms
        assert page.locator("#tree li[data-id]").count() == 1060
        filter_ms = page.evaluate(
            """() => { const q = document.getElementById('q'); const t = performance.now();
               q.value = 'historia 3.2'; q.dispatchEvent(new Event('input'));
               return performance.now() - t; }"""
        )
        assert filter_ms < BUDGET_FILTER_MS, filter_ms
        assert page.locator("#ex-count").inner_text().startswith("4 ")  # stories 3.2.0 to 3.2.3
        page.click("#tree li[data-type=story]:visible a.lbl >> nth=0")
        assert page.locator("article.item.is-active").count() == 1
        print(f"\nscale: load {load_ms:.0f} ms, filter {filter_ms:.0f} ms")
        browser.close()
