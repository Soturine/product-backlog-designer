# Product Backlog Designer (PBD)

**From requirements to validated, traceable and actionable backlogs.**

[Português (Brasil)](README.pt-BR.md) · [Documentation](docs/README.md) · [Roadmap](docs/roadmap.md) · [Example dashboard](examples/demo/report.html) · [Research and code audit](docs/upstream-code-audit.md)

> **Development status:** pre-alpha. Agent-led generation from zero is implemented and was dogfooded on 12 synthetic cases (readers, generator and independent reviewer as separate agents; see [M1 evidence](docs/evidence/M1.md)): `pbd` runtime with verified reader ledgers, claims, design, independent review, verified quality gates, offline HTML report, JSON/Markdown/CSV/XLSX exports and a local Azure DevOps package. Audit, compare, refinement, planning, incremental ADR updates and any tracker publication are not implemented. Nothing contacts a tracker.

## Why PBD?

A requirements document is not yet a backlog. A backlog can look complete while missing a rule, exception, constraint or acceptance condition. PBD is designed to turn explicitly selected sources into a coherent plan, audit that plan independently, and publish approved work items without losing formatting, links or human decisions. It serves product owners, analysts, engineering teams, project managers and QA across domains.

One skill owns functional and technical backlog planning. [Functional Test Designer](https://github.com/Soturine/functional-test-designer) remains independent for functional Test Cases. The original requirements remain authoritative for both.

## The normal workflow

1. Put the sources in a private working directory and tell the agent what to read, or write a short [instructions.md](docs/instructions.md).
2. Ask the agent: **"Generate the complete backlog from these requirements and prepare a local Azure DevOps package."**
3. Open the HTML report, inspect the complete work-item tree, criteria, questions, findings and coverage. Resolve only material ambiguities.
4. If publication is desired, review the exact destination and proposed changes, then approve that plan. The runtime will apply and read back the results.

No need to invoke separate commands for source analysis, story writing, tasks, quality checks and rendering. They are internal stages. The preferred future agent entrypoint is `/pbd`; ordinary language is equally valid. Existing specialized entrypoints remain optional power-user controls. See [interaction contract](docs/usage.md).

### Minimal private instructions

```md
Read only docs/PRD.pdf and docs/TDD.pdf.
Generate Epics, Features, User Stories, acceptance criteria and Tasks.
Audit against the original requirements.
Language: Portuguese (Brazil).
Target: Azure DevOps Agile.
Output: HTML, JSON and local Azure import package.
Do not publish remotely.
```

Generation from scratch is the primary mode: an existing backlog is optional, never a prerequisite. Sources, language and scope can be supplied directly in chat instead. Technical sources and tracker credentials are optional for local generation. The skill must not invent their contents.

## Capabilities

| Mode | Result |
|---|---|
| Generate | Epics, Features, Stories, criteria, Tasks, dependencies and suggested priorities |
| Audit | Individual source/claim/item/criterion/task review, evidence, ambiguities, conflicts and unsupported additions |
| Compare | Independent backlogs aligned by semantic obligations, not title or item count |
| Refine | Targeted improvements, profile learning and change proposals |
| Plan | Estimates, risk, value, capacity and sprint suggestions when inputs support them |
| Evolve | PRD/ADR changes, impact, stable IDs, reconciliation and minimal updates |
| Publish | Azure discovery, snapshot, validated package, approval, apply, read-back and receipt |

Support Agile, Scrum, Basic, CMMI and custom process profiles; discover actual destination rules. GitHub and Jira are future adapters. Generate only selected levels when asked. Never fabricate dates, assignees, completed work or business values.

## What work items look like

**Epic:** objective, context, scope, exclusions and intended outcome.  
**Feature:** meaningful capability, value, related rules and child stories.  
**User Story:** **As a** library member, **I want** to reserve an available book, **so that** I can borrow it later.  
**Acceptance criteria:** an available title can be reserved; a title without available copies cannot be reserved.  
**Tasks:** implement reservation validation; implement persistence; verify both outcomes.

The example assumes the behavior is in the fictional source. Unknown reservation duration becomes a question, not a fabricated rule. Portuguese stories use **Eu como**, **gostaria que**, **para**; native HTML preserves bold and lists. Acceptance can be rendered as a native HTML table (ID, criterion, expected outcome), list or Gherkin. Alternative formats and enablers are supported when suitable. See [work items](docs/work-items.md), [story engineering](docs/story-engineering.md), [acceptance engineering](docs/acceptance-engineering.md).

## See the report

Screenshots of a real `report.html` produced by the agent-led dogfood of a synthetic PRD (case [c01-prd-only](benchmarks/runs/m1/c01-prd-only/)).

| Executive layer | Technical layer (work item detail) |
|---|---|
| ![Executive summary](docs/images/report-summary.png) | ![Backlog tree with item detail](docs/images/report-backlog.png) |
| ![Quality gates](docs/images/report-gates.png) | ![Dark theme](docs/images/report-dark.png) |

Open the interactive file yourself: [benchmarks/runs/m1/c01-prd-only/report.html](benchmarks/runs/m1/c01-prd-only/report.html) (GitHub shows HTML as source: download it, or clone the repository, and open it in any browser; it is a single offline file with no external requests). Reports for all 12 dogfood cases are in [benchmarks/runs/m1](benchmarks/runs/m1/).

## Output

```text
pbd-output/
  report.html                 # default human entry point, offline
  backlog.json                # canonical backlog and field provenance
  findings.json               # audit findings and evidence
  questions.json              # unresolved decisions
  traceability.json           # sources → claims → work items → criteria/tasks
  metrics.json                # honest counts, denominators and gates
  manifest.json               # versions, hashes, run status
  azure/
    azure-import.json         # local canonical package, not raw CLI input
    azure-import.csv          # optional portal-compatible subset
    publication-plan.json     # exact target-bound preview
    publication-result.json   # actual receipt, only after apply
```

Markdown, CSV, XLSX, dependency diagrams, comparison, sprint report and FTD handoff are optional or mode-dependent. A generated local package is not a published backlog. [Output specification](docs/reporting.md) · [Azure integration](docs/azure.md) · [Synthetic example JSON](examples/demo/backlog.json).

## Architecture

```mermaid
flowchart LR
 A[Selected sources] --> B[Source inventory and readers]
 B --> C[Atomic claims and domain model]
 C --> D[Semantic planning]
 D --> E[Independent review]
 E --> F[Canonical runtime and gates]
 F --> G[HTML and JSON]
 F --> H[Local Azure package]
 H --> I[Exact plan approval]
 I --> J[Apply and verify]
 F --> K[Independent FTD handoff]
```

Agent-first: agents interpret actual source content. Deterministic Python owns identity, contracts, graphs, validation, persistence, rendering and transport. Local-first: no mandatory external database, server, paid API or Docker. Domain-agnostic, tracker-agnostic and privacy-first. [Architecture](docs/architecture.md) · [Reuse strategy](docs/upstream-code-audit.md).

## Assurance

Eighteen planned quality gates (original thirteen plus five extensions) distinguish structural validity from semantic coverage. Each claim gets a disposition; each work item and criterion is checked in reverse against evidence. INVEST, QUS-inspired review, Example Mapping, EARS and Gherkin are tools, not rigid templates or scores. No fixed number of items or acceptance criteria. Unknowns remain visible. Benchmark comparisons with HVE Core, BMAD, Spec Kit, Task Master and bare agents require independent gold, equal conditions where feasible, holdouts, mutations and honest metrics. [Gates](docs/quality-gates.md) · [Benchmarks](benchmarks/README.md).

## Integration and safety

Azure CLI authentication with REST/JSON Patch for lossless writes; optional CLI and portal CSV paths. Always read and discover fields first, match stable identity, preview changes, require exact-plan approval, verify remote revisions and read back. No automatic deletion, rule bypass or silent overwrite. [Azure](docs/azure.md) · [Security](docs/security.md).

## Roadmap and development

| Milestone | Scope | Status |
|---|---|---|
| M0 | foundation, schemas, runtime contracts, reuse decisions | runtime foundation done ([evidence](docs/evidence/M0.md)); profiles and gold fixtures moved to M1 |
| M1 | generation and default report/package workflow | substantially complete ([evidence](docs/evidence/M1.md)); open: new-session end-to-end run, Linux symlink tests |
| M2 | audit, compare and profiles | planned |
| M3 | Azure export and verified publication | planned |
| M4 | planning and capacity | planned |
| M5 | incremental changes | planned |
| M6 | ecosystem and benchmark qualification | planned |

See [roadmap](docs/roadmap.md), [skill](SKILL.md), [changelog](CHANGELOG.md), [attribution](ATTRIBUTION.md). Public examples must be synthetic; never commit private sources or credentials. Repository license selection is pending; no third-party implementation has been vendored. Contributions and runtime installation instructions will be qualified before release.

## Implementation directive
[Agent-led execution](docs/agent-led-execution.md) · [Evidence and backlog health](docs/evidence-and-backlog-health.md) · [Calibration protocol](benchmarks/calibration.md) · [Master directive](docs/PBD_AGENT_LED_MASTER_DIRECTIVE.md). All implementation and qualification work is offline; live tracker access remains unqualified and requires separate authorization.
