# Agent / runtime boundaries (audit, 2026-11-25)

Principle: **agent-first, native-first, runtime-verified, minimal dependencies, evidence-driven.** Anything that needs comprehension, interpretation, judgment or creativity belongs to the agent; anything that needs exactness, integrity, security or reproducibility belongs to the runtime. In hybrid steps the agent proposes with provenance and the runtime checks explicit constraints and persists. A valid schema never establishes semantic truth, and no gate passes on agent confidence alone.

Audit of the current implementation (grouped by responsibility; decisions: KEEP, SIMPLIFY, DELEGATE, OPTIONAL_FALLBACK, REMOVE_REDUNDANCY).

| Responsibility | Where | Owner | Finding | Decision |
|---|---|---|---|---|
| Reading sources | `extract.py`, `procedures/reader.md`, work order | agent (native) | Extracted text was the reader's primary input; a PDF text layer could pass for a complete reading. | **OPTIONAL_FALLBACK** for extraction (kept for line locators, mechanical quote checks and fallback); originals are now the primary input, readers declare method/tool/limitations, PDFs and images are never `read` from extracted text, transcription-only evidence is labelled (commit 4b6f456). |
| Quote and locator verification | `reading.py` | runtime | Correct and cheap; distinguishes mechanical vs transcription evidence. | KEEP |
| Inventory, digests, scope, archive limits | `sources/`, `security/` | runtime | Correct. | KEEP |
| Obligations, ambiguity, conflicts, design, review, INVEST, duplicates, task sufficiency | procedures + submission contracts | agent | The runtime only validates references, coverage dispositions, denominators and completeness; no keyword or regex semantics found. | KEEP |
| Templated-output guard, visible-ID references, confirmed-on-ambiguous rejection | `design.py` | runtime guards on agent output | Mechanical checks of explicit contracts, not judgments. | KEEP |
| Duplicate titles | `modes.check` | runtime → agent | Reported only as candidates; equivalence is the reviewer's call. | KEEP (candidates only) |
| Profile inference | `modes.infer_profile` | hybrid | Counts and frequencies only, emitted as an unverified draft; never applied automatically. Interpreting whether a convention is desirable is agent/owner work (documented). | KEEP |
| Planning | `planning.py` | hybrid | Arithmetic, cycles, capacity, units and formulas are runtime; complexity, risk, estimates and priorities come in as confirmed fields or as labelled proposals from the agent/user. A schedule is one proposal. | KEEP |
| Source diff classification | `evolution.diff_sources` | hybrid | `formatting_only` claimed an administrative change from normalized-text equality, which says nothing about figures, layout, drawings or cell formats. | **SIMPLIFY**: renamed `text_equivalent`, flagged `needs_agent_review` with what was not compared; meaning of every change is agent work. |
| Evolution / refinement application | `refine.py`, `evolution.py` | runtime | Approvals, digests, lineage, stale checks, non-destructive apply; deciding what to change is the agent's proposal. The exact-title re-creation guard accepts `new_identity_reason`. | KEEP |
| Comparison | `compare.py` | agent decides, runtime validates | Mappings, relations and dispositions are the agent's; the runtime validates keys, quotes and completeness and derives counts. | KEEP |
| G15 on imported backlogs | `gates_engine.py` | runtime + reviewer evidence | Supersession reported by the reviewer could sit behind a G15 PASS (imported work has no claim trace). | **FIXED**: confirmed reviewer findings tagged G15 fail the gate; the PASS reason states the reviewer-only assessment. |
| Report and exports | `render/` | runtime | Deterministic, offline, localized; the agent never writes HTML. | KEEP |
| Gate reasons | `gates_engine.py`, catalogs | runtime | Localized through `gx.<gate>.<status>` codes; the raw message is kept as technical detail. | KEEP |
| Execution profiles / models | `core/execution.py` | host | Capability tiers, no hard-coded vendor model. | KEEP |

Not changed on purpose: no OCR, converters or document interpreters were added; no extractor useful for verification, security, portability or fallback was removed; the runtime remains usable on its own for structural checks and artifacts, with one runtime dependency (`jsonschema`, plus optional `pypdf`/`playwright`).

## Measurements
See [evidence M3–M6](evidence/M3-M6.md#native-first-and-boundary-audit-measurements): measured before/after on the same synthetic fixtures; agent-side token and time costs are only reported when the host exposes them.

## Selective QE knowledge transfer (2026-11-25)

The current native-first reader and independent reviewer already own the reading/design boundary. Do not introduce QE's extraction pipeline, project model, semantic provider or test generator. Extend the existing method only where evidence changes a backlog decision.

- Source identity, read integrity, authority, freshness, confidence and importance are separate. Inventory and verified quotes do not prove that all visual content was understood or that a proposed story follows from it. Use original host-native reading where possible; use extracted text for exact citation verification and disclosed fallback. Prefer on-demand extraction if a later measured change preserves existing gate integrity.
- Distinguish obligations from proposed improvements and risk hypotheses. A credible risk may justify a proposed work item or question; it does not create a mandatory acceptance criterion. Preserve conflicting claims and record who can resolve them. Never promote current implementation, historic backlog or model confidence into contract.
- For existing/reused backlog, keep source identity, revision, relationships and prior history; review destination assumptions, dependencies, actor permissions and acceptance criteria before claiming reuse. Propose deltas without deleting or silently rewriting history. A stale source invalidates dependent conclusions until reviewed.
- Treat project model concepts (actor vs auth role, state/transition/guard, interfaces, side effects, invariant) as optional semantic lenses rather than a second mandatory schema or template. Use the project's existing vocabulary. Do not turn the PBD into a functional test generator; handoff remains context/seeds and FTD independently reads its authority.
- Measure atomic obligation/criterion coverage separately from work-item volume, missing-source errors, unsupported acceptance criteria, duplicate/redundant proposals and independent-review accuracy. Report unknowns and per-source limitations; never turn a gate pass into proof of semantic completeness.

Qualification candidates (NOT_RUN): source with diagram-only obligation; equivalent paraphrases; conflicting authority vs implementation; reused story with changed target role; stale source invalidating a criterion; high-risk scenario with no normative threshold. Compare against independent gold; retain existing G01–G18 semantics, do not invent additional mechanical gates or claim current gates prove these cases.

Concepts adapted from [QE Trust Model](https://github.com/Soturine/qe-engineering-skill/blob/main/docs/TRUST_MODEL.md), [Project Model](https://github.com/Soturine/qe-engineering-skill/blob/main/docs/PROJECT_MODEL.md), [Oracle Policy](https://github.com/Soturine/qe-engineering-skill/blob/main/docs/ORACLE_POLICY.md) and [Existing Asset Audit](https://github.com/Soturine/qe-engineering-skill/blob/main/docs/EXISTING_ASSET_AUDIT_POLICY.md). External reference: [Agent Skills specification](https://agentskills.io/specification) and [Anthropic effective agents](https://www.anthropic.com/research/building-effective-agents). Documentation and agent guidance only; no runtime changes.
