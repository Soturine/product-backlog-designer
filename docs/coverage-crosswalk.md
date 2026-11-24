# Design coverage crosswalk

This is a planning inventory, not proof of implementation. It consolidates the agreed product scope without project-specific source material.

| Capability | Design owner | Milestone |
|---|---|---|
| Single skill, natural language and optional commands | [usage](usage.md), [skill](../SKILL.md) | M0–M1 |
| Scoped multi-source readers, one per declared source | [methodology](methodology.md), [architecture](architecture.md) | M0–M1 |
| PRD/BRD/TDD/ADR/code/backlog/manuals/notes/policies | [instructions](instructions.md) | M0–M1 |
| Atomic requirements, domains, hierarchy, tasks, criteria | [methodology](methodology.md), [work items](work-items.md) | M1 |
| Rich HTML, pt-BR/EN, templates, field provenance | [work items](work-items.md), [reporting](reporting.md) | M1–M3 |
| INVEST, QUS, 3Cs, EARS, Gherkin, Example Mapping, SPIDR | [story engineering](story-engineering.md), [acceptance engineering](acceptance-engineering.md) | M1–M2 |
| Complete item and criterion audit, reverse mapping, compare, profiles | [quality gates](quality-gates.md), [commands](commands.md) | M2 |
| JSON, HTML, MD, CSV, XLSX, dependencies, questions, metrics, FTD handoff | [reporting](reporting.md), [commands](commands.md) | M1–M6 |
| Azure export, schema discovery, field mapping, CLI package, preview, apply, verify | [Azure](azure.md) | M3 |
| Priority, risk, value, estimates, sprint planning and capacity | [planning](planning-engineering.md) | M4 |
| ADR, stable IDs, diffs, conflict protection and incremental change | [architecture](architecture.md) | M5 |
| Other trackers and agent hosts | [roadmap](roadmap.md) | M6 |
| Competitive research, code reuse, license checks, benchmark baselines | [market research](market-research.md), [source audit](upstream-code-audit.md), [benchmarks](../benchmarks/README.md) | M0–M6 |
| Canonical schemas, stable identity, source safety, run state, offline guard (runtime) | [ADR-0001](decisions/ADR-0001-m0-foundation.md), [threat model](threat-model.md), [M0 evidence](evidence/M0.md) | M0 (implemented) |
| Privacy, no remote writes without approval, no fabricated claims | [security](security.md), [quality gates](quality-gates.md) | all |

All planned capabilities remain unqualified until corresponding exit evidence exists. Scope and omissions must be visible in every run.
