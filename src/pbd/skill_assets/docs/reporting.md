# Report and artifact product specification

## Default artifacts
One entry point: `report.html`. `backlog.json` is the canonical exchange representation; `findings.json`, `questions.json`, `traceability.json`, `metrics.json`, `gates.json` and `manifest.json` provide evidence. Comparison runs write `comparison.json`/`comparison.md`; refinement writes `refinement-plan.json`, `refinement-diff.md` and, after approval, `backlog.refined.json` with `refinement-result.json`. Other formats are selectable. The renderer never re-interprets semantic data and there is one source of truth per fact.

## Information architecture
One design system and one shell serve every mode; navigation shows only the views that have data (no empty tabs or fake buttons).

| View | What it answers |
|---|---|
| Overview | A sentence filled from recorded counts (never a new conclusion), the gate state, readiness split into backlog content, source reading, independent review and tracker integration, key figures with denominators and definitions, item composition, obligation dispositions and findings by severity (interactive legends filter the target view), what needs a decision, what is not proven. Audit runs add a note that failing gates are audit results. |
| Backlog | Master/detail explorer: compact hierarchy or table on the left, item detail on the right. Accent-insensitive search over ID, key, title, description and criteria with highlighted matches; ancestors of a match are shown as context and not counted; filters by type, review verdict, source support and origin combine and show as removable chips; expand/collapse all or down to a level; keyboard arrows in the tree; deep links `#item-<ID>` and `#crit-<ID>`; on mobile, list → detail → back keeps the filters. |
| Item detail | Type, review verdict and source support, ancestors, title, key and canonical ID with copy ID/link, rich description, each acceptance criterion with visible ID, status, review and claim links, child items, fields with state (confirmed/proposed/unknown...) and rationale, source requirements with original quotes and locators, dependencies, independent review with INVEST and task sufficiency, related findings and questions, technical JSON on demand. |
| Requirements | The independent inventory (obligation, original quote and locator, disposition, covering work, matched claims, rationale) and reconciled claims, both filterable by disposition and source; decisions and the claims they supersede. |
| Findings & questions | Findings by severity with expected/actual/why/impact/recommendation, classification, review status, gate and affected work; questions grouped blocking/non-blocking with impact, options and affected items. A visual interaction never records a decision. |
| Quality & evidence | The 18 gates with localized names and explanations, status filter, denominators with provenance, evidence kind (deterministic check, independent review, ...), hashes with copy, and the raw runtime message. G17/G18 explain that nothing was published. |
| Sources | Each selected source with authority, read status, members, digests; limitations. |
| Integration package | Exact native fields per work item (description and acceptance kept separate), proposed values not written, profile verification state. Always marked local only. |
| Comparison (compare runs) | Both baselines side by side over the shared inventory, obligation-by-obligation alignment with agreement filter, many-to-many correspondences with relation, cardinality and differences, unmatched and unsupported entries, findings per side. No winner or score. |
| Data | The complete canonical JSON with a local download. |

## Metrics without misleading UI
- Each metric shows its denominator and provenance; a tooltip defines it. Example (c01 re-render): **12/15 fully covered** (COVERED over the reviewer's inventory) next to **15/15 handled per G02** (covered or dispositioned by contract: out of scope, superseded, deferred, question).
- Unknown is never shown as zero; populations with different denominators are never summed; counts keep their canonical codes in data and human labels in the UI ("7 propostos").
- The gate state sentence excludes integration gates (G12/G17/G18), so a local generation is not shown as failed because nothing was published; integration readiness is reported separately as "not proven".

## Internationalization
- Interface language, artifact language and source language are separate. Catalogs `src/pbd/render/locales/{pt-BR,en,es}.json` hold every UI string, enum label, gate name and explanation (437 keys each); a test enforces identical keys, placeholders and plural forms. Plural forms follow CLDR one/other with an explicit zero phrase ("Nenhuma pergunta bloqueante"). Fallback: `en`; a key missing from `en` fails.
- The default interface language follows the run language. The language selector switches offline using the catalogs embedded in the page; `lang` attributes keep backlog content, quotes and runtime messages (English) marked correctly. Switching the interface never claims to translate the backlog; a toast says so.
- Gate explanations use catalog codes (`gx.<gate>.<status>` or `gx.<status>`); the raw runtime message is preserved in the technical detail.

## Interaction and motion
Micro-interactions 120–200 ms (hover, pressed, focus, chips, copy feedback, tree chevrons, tooltips) and layout transitions 200–260 ms (view change, sidebar collapse, mobile drawer, detail panel), using transform and opacity only. No infinite animation, no animated counters, no fake loading. `prefers-reduced-motion: reduce` disables every animation and transition. Escape closes the drawer and restores focus; tooltips open on hover and keyboard focus.

## Technical design
- `src/pbd/render/report_html.py`: view model + server-side components for every view (core content readable without JavaScript); `i18n.py`: catalogs, plurals, number formatting; `assets/report.css` and `assets/report.js`: packaged, inlined, allowed by CSP **hash** (`style-src` and `script-src` both by SHA-256; no inline style attributes or handlers; `default-src 'none'`).
- No CDN, fonts, analytics, images or requests; works from `file://`. Embedded JSON escapes `<`, `>` and `&`; descriptions pass the sanitizer allowlist; `javascript:` links are dropped.
- Copy uses the Clipboard API with a selection fallback and an explicit message when the browser refuses; downloads are real local Blob downloads; print hides navigation and can include technical detail on request.
- Theme (system/light/dark) and interface language persist only for the browser session.

## Performance budgets
Measured on the baseline host (Windows 11, Edge) with 1,060 synthetic items and 400 criteria: HTML ~5.6 MB, render ~0.2 s, browser load ~1.7 s, search filter ~16 ms. Budgets enforced by `tests/e2e/test_report_scale.py`: < 7 MB, render < 3 s, load < 6 s, filter < 300 ms. No virtualization is needed at this volume; all items stay searchable.

## Quality requirements
- Count every canonical item and criterion exactly once; HTML counts, criteria and gate states are compared with the JSON in Playwright tests.
- HTML sanitization, escaping, safe href schemes and script-safe embedded JSON; hostile titles and descriptions never execute (tested).
- Deterministic render from versioned input; Playwright tests for navigation, deep links, history, search, filters, chips, tree, table view, language switch, copy, download, mobile list/detail, drawer, keyboard, reduced motion, no-JS rendering and no network.
- Clear distinction between synthetic examples, re-renders, audits, planned changes and (future) verified publication.

## Screenshots and examples
- Synthetic examples: [examples/reports](../examples/reports/README.md) (`python tools/build_examples.py`), fixture reproductions of generation, audit and comparison.
- Captures: [docs/images/report](images/report/) (`python tools/screenshot_report.py`) at 1440/1280/768/390/320 px, light/dark, PT/EN/ES, plus `report-demo.png`, an animated PNG of a short local flow (no video encoder is available on the baseline host).
- Before: the M1 renderer captures in [docs/images/before-m2](images/before-m2/).
- Re-renders of the recorded M1 runs: [benchmarks/rerender/m1](../benchmarks/rerender/m1/README.md) (`python tools/rerender.py`), labelled as re-renders; the recorded runs are unchanged.

## Accessibility
Target: WCAG 2.2 AA as a verifiable goal, not a claim. Implemented: landmarks (header, nav, main), skip link, one `h2` per view, labelled controls, visible focus, status text plus icon (color is never the only signal), tooltips reachable by keyboard, reduced motion, reflow without horizontal scroll down to 320 px. No automated scanner (axe-core) is installed on the baseline host; a full accessibility review is part of the final qualification ([ledger](../benchmarks/qualification-ledger.json)).
