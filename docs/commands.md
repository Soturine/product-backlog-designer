# Command and artifact contracts (planned)

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
