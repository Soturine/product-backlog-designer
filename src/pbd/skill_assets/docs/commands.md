# Command and artifact contracts (planned)

The preferred interface is natural language or `/pbd` (umbrella entrypoint). Automatically run the relevant internal stages. The commands below are optional expert controls, not prerequisites. See [usage](usage.md).

| Agent command | Purpose |
|---|---|
| /pbd-gen | generate complete or selected levels |
| /pbd-audit | review existing backlog against authorities |
| /pbd-compare | compare independent or existing backlogs |
| /pbd-refine | propose targeted revisions |
| /pbd-check | run applicable gates |
| /pbd-clarify | report questions and decisions |
| /pbd-render | regenerate local reports |
| /pbd-plan | dependency and sprint planning |
| /pbd-adr | incorporate approved decisions |
| /pbd-diff | source/version impact |
| /pbd-profile | infer and review conventions |
| /pbd-azure-export | read-only snapshot |
| /pbd-azure | local import package |
| /pbd-azure-publish | prepare/apply approved plan |
| /pbd-azure-verify | read-back fidelity |
| /pbd-benchmark | execute controlled evaluation |

Selective scope: `--only epics,features`, `stories,acceptance`, `tasks`, `hierarchy`, `sprints`. A partial run must disclose omitted scope and preserve context dependencies. CLI runtime `pbd` is planned; slash commands are agent entrypoints, not assumed installed.

## Outputs
Canonical JSON: backlog, requirements, claims, acceptance-criteria, traceability, dependencies, sprint-plan, findings, questions, metrics, source manifest. Local Markdown: backlog, questions, executive-summary. CSV/XLSX: backlog and traceability, sheets by item type. Mermaid: dependencies.mmd. Offline HTML: report, comparison, audit-report, sprint-plan; responsive, search/filter, expandable complete tree, native-field preview, source locators, side-by-side expected/actual/why/impact, individual criterion and task disposition, export/print, accessible contrast. Azure folder: azure-snapshot.json, azure-export-package.json, azure-import.json, azure-preview.json, publication-plan.json, publication-result.json. Handoff: ftd-handoff.json (source/claim/item/criterion IDs, questions and confirmed decisions, real tracker links only when verified). .pbd/current-run.json and .pbd/runs/ for private state. Produce only applicable outputs and manifest; no fabricated artifacts.

Default output is report.html and backlog.json with supporting evidence JSON and manifest. Azure-selected generation produces a local import package automatically when applicable; no remote mutation. See [reporting](reporting.md) and [Azure CLI package](azure.md).

## FTD handoff and traceability map
`pbd handoff ftd --backlog backlog.json --out handoff/` writes `ftd-handoff.json` (handoff 1.1: every seed starts with the canonical criterion ID, `[PBD-AC-… · CA-01] …`, and lists `pbd_ids`) and `ftd-instructions.md`, a draft instructions file for Functional Test Designer that keeps those IDs. After FTD has designed its Test Cases, `pbd handoff ftd-map --handoff handoff/ftd-handoff.json --ftd-test-cases <ftd output>/test-cases.json [--backlog backlog.json] --out map/` writes `ftd-map.json`: for each FTD seed disposition, the PBD IDs found **exactly** in the seed text, FTD's test case IDs and disposition, many-to-many links per PBD ID, counts of linked / unresolved / dangling seeds, designed vs executed test cases (FTD designs; nothing is executed), duplicate anchors and staleness against the backlog. Seeds without a known canonical ID stay unresolved (no title or text matching); handoffs before 1.1 only carried visible IDs such as `CA-01`, so their links cannot be resolved. The map is planning traceability, not coverage evidence; the original sources remain FTD's authority, and FTD itself stores no PBD field (native propagation is not implemented).

