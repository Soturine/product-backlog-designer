# Report and artifact product specification

## Default artifacts
One entry point: report.html. backlog.json is the canonical exchange representation; findings.json, questions.json, traceability.json, metrics.json and manifest.json provide evidence. Other formats are selectable. Never re-interpret semantic data inside the renderer. No duplicate divergent sources of truth. Mode-specific outputs are listed in [commands](commands.md).

## HTML design
Use an original or properly attributed adaptation of the two-layer assurance design from Assertiva and the FTD offline report. Layer 1 answers in plain language: what was reviewed, what is sound, what differs, why it matters, what needs decision, and what is not proven. Layer 2 exposes every source, claim, Work Item, field, acceptance criterion, task, relation, finding, gate and metric. No executive summary can hide a blocked critical item.

Design system: neutral canvas, clear typography, restrained color for severity and item type, accessible contrast, responsive layout, keyboard navigation, visible focus, light/dark theme, meaningful empty/blocked states, no external fonts/scripts/network. Support printing and offline operation; core content visible without JavaScript. Use semantic HTML details/summary, tables and links. Avoid decorative charts that imply evidence not collected.

Views: executive summary, navigable complete backlog, work-item detail with Azure-like fields (rich description/criteria separately), source-to-claim matrix, item and criterion audit, findings with expected/actual/why/impact/recommendation, questions and decision history, dependencies, suggested sprint plan, comparison, source inventory, publication preview/receipt. Search by ID, title, criterion and text; filters by type, severity, disposition, source, sprint; expand/collapse tree. Charts show actual denominators, unknowns and scope. Links to tracker only from verified IDs. Include optional full canonical JSON disclosure and accessible downloads/print, with privacy warning.

## Quality requirements
- Count every canonical item and criterion exactly once in its primary inventory; relations may reference but not duplicate them.
- Verify full coverage of item fields, not only findings or aggregate metrics; absent values remain absent.
- HTML sanitization, escaping, safe href schemes and script-safe embedded JSON; no source-driven execution.
- Deterministic render from versioned input; schema checks, artifact hashes, golden fixture snapshots, cross-format counts, accented text round-trip, Playwright keyboard/mobile/search/filter/no-network tests, XSS/CSV injection tests.
- Provide clear distinction between synthetic demo, real audit, planned changes and verified publication.
- Preview of exact native Azure field values, including bold story prefixes and separate acceptance criteria.

See [synthetic design demonstration](../examples/demo/report.html) and [sample JSON](../examples/demo/backlog.json). The demo is original static example content, not the finished renderer.
