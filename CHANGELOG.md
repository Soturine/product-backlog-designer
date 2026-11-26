# Changelog

## Unreleased — corrective round: readiness, report review tool, team planning
- Backlog schema 1.2.0 (additive): agent-judged item readiness with typed `blocked_by`/`independent_of` links; runtime rejects readiness contradictions; reviewer `readiness_check`; G08 reflects readiness; planning never schedules blocked work (QL-019). Pre-1.2.0 artifacts stay valid and show as not assessed.
- Reviewer prose may cite design keys (rendered as links) but not per-story visible criterion IDs (QL-004 residual); the designer procedure no longer suggests citing criterion keys in text; the orchestrator procedure routes audit/compare/refine/plan/evolve/mock publish.
- Report: development readiness on the overview and per item, readiness filter, per-gate purpose/why/evidence type/status meaning/affected work/next step and a glossary, plain G02/G08 counts, presentation-only Generic/Azure DevOps/Jira appearance with original pictograms, sortable table with column visibility.
- `pbd plan` team plans: user-supplied team and capacity per person and unit, responsibility modes, agent-proposed placement/owners/assignees checked by the runtime, actual snapshot kept separate, plan-level G10; parent and child estimates never added. Plan report with sprint goals, owner/assignee board, load by person, story → tasks, unassigned/unallocated work and build order vs backlog position.

## Unreleased — M3–M6: mock Azure workflow, planning, evolution, FTD handoff
- M3: local Azure snapshots and discovered profiles; prepare/preview/approve/apply/verify against an in-memory mock only, with journal, idempotency, reconciliation, bounded retries and read-back; publication report. No live transport exists.
- M4: `pbd plan` — dependency order, MoSCoW/RICE/WSJF only with complete inputs, sprints only with known capacity, dates only from a user calendar, scenarios, checks, staleness; plan report.
- M5: `pbd evolve` — source diffs (formatting-only vs content), decisions superseding claims, retrace, supersede, split/merge lineage, human-edit protection, no deletion, stale-artifact detection; evolution report.
- M6: `pbd handoff ftd`; integrated flow test across every mode; wheel and sdist qualified in clean environments; install, hosts, troubleshooting and roadmap status tables; evidence in docs/evidence/M3-M6.md.

## Unreleased — M2: M1 fixes, audit and comparison modes, premium report
- M1 dogfood fixes: confirmed criteria/fields cannot trace only ambiguous, conflicting or unknown claims; container-only obligations are signalled; visible criterion IDs in text are rejected; source-stated field values are data obligations; skill assets ship in the wheel. One qualification ledger tracks open items.
- Import of existing backlogs (PBD JSON, `pbd.import` JSON, CSV) with fail-closed type mapping; `audit` and `compare` modes over local baselines; `refine` (plan, diff, approve keys, apply; no deletion); `check`, `clarify`, `profile show|infer|execution`; execution profiles economical/balanced/rigorous.
- Report rebuilt: sidebar and mobile drawer, routing and deep links, executive overview with readiness by concern and metrics with denominators, master/detail backlog explorer, requirements, findings, gates with evidence, sources, integration preview, comparison views; offline pt-BR/en/es interface; reduced-motion support; CSP by hash for style and script; core content without JavaScript; budgets at 1,060 items.
- Examples, re-renders of the recorded M1 runs (labelled), 15 screenshots and an animated demo; evidence in docs/evidence/M2.md. Semantic requalification deferred to the final integrated qualification.

## Unreleased — M0 corrective round and M1 agent-led generation
- Gate evidence is verified against artifact hashes, run and stage; coverage denominators carry hash-bound inventories and disposition breakdowns; G13 requires deterministic evidence of complete, independent review.
- Agent-led pipeline: `pbd start`, verified reader ledgers (one reader per declared source, quotes checked against cited lines and pages), claims reconciliation, design, independent review, `pbd finalize`; work orders describe each next stage.
- Sources: UTF-8/UTF-16/cp1252 text, DOCX (headers, footers, notes, comments), XLSX, PDF text layer (optional pypdf), images as visual members; gaps can never be certified as read without a vision transcription.
- Outputs: two-layer offline report.html (Assertiva design tokens), canonical JSON and projections, Markdown, CSV, XLSX, Mermaid, local Azure package; process profiles for generic, Azure Agile, Scrum, Basic and CMMI.
- Skill: procedures for orchestrator, readers, designer and reviewer; `pbd skill install`; discovery verified in a fresh Claude Code session.
- Dogfood: 12 synthetic cases with pre-registered gold, separate reader, generator, reviewer and evaluator agents; 90 gold obligations, 0 missed, 80/81 critical; two thresholds missed and reported. Eleven defects found and fixed with regressions.

## Unreleased — M0 runtime foundation
- Add `pbd` Python package (3.11+, sole runtime dependency `jsonschema`) and offline CLI: `doctor`, `schema`, `validate`, `inventory`, `id`, `run`, `privacy-scan`.
- Add strict versioned v1 JSON Schemas: backlog (sources, claims, items, criteria, relations, questions, decisions, findings, field provenance, temporal supersession, typed evidence), run manifest, gate report (G01–G18), publication plan (no DELETE) and receipt (mock never live-verified).
- Add opaque stable identity, canonical JSON digests, referential invariants (duplicates, dangling refs, parents, cycles, stale locators, namespace mixing), gate evidence rules, atomic state with hash-chained journal and checkpoint invalidation.
- Add source allowlist with traversal/symlink/junction rejection and in-place archive inspection limits; in-process zero-network guard; privacy scanner; default-deny remote-write authorization.
- Add unit, property, contract, security and docs-link tests with synthetic fixtures; ADR-0001, threat model, install guide, upstream pins and M0 evidence. No generation, rendering, tracker access or release.

## Unreleased — design baseline
- Define single agent-first skill, architecture, quality gates and source-first methodology.
- Specify native rich text, field provenance, profiles and Azure export/publication contracts.
- Document market references, benchmarks, synthetic fixture and implementation roadmap.
- No runtime, remote adapter, benchmark results or release claimed.

- Expand story and acceptance engineering, task planning, research bibliography and evaluation scenarios; specify mode-specific agent procedures.

- Expand bilingual README, single-entrypoint interaction contract, output/report design, Azure CLI bundle, targeted upstream implementation and license audit, reuse decisions and synthetic dashboard example. No upstream code vendored or runtime qualified.

- Specify source-only default, agent-led execution boundaries, evidence/temporal health, native table acceptance, offline calibration and implementation directive; extend quality gates without renumbering. No runtime or live integration executed.

- Require per-checkpoint commits, pushes, remote verification and authorized Git identity; prohibit AI authorship trailers and unnecessary CI, preserve required attribution and branch protections.
