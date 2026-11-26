# Quality gates

Every gate records status PASS, FAIL, BLOCKED, NOT_RUN or NOT_APPLICABLE, scope, evidence, validator version and reason. Structural validity never proves semantic completeness.

| Gate | Required evidence | Kind |
|---|---|---|
| G01 Source Integrity | expected vs read inventory, hashes, omissions | mixed |
| G02 Requirements Coverage | independent claims and explicit dispositions | mixed |
| G03 Hierarchy Integrity | unique IDs, allowed parents, no cycles/orphans | deterministic |
| G04 Traceability | resolvable source/claim/criterion/task links | mixed |
| G05 Story Quality | justified INVEST review, value and granularity | semantic |
| G06 Acceptance Quality | observable conditions, complete relevant behavior | semantic |
| G07 Task Coverage | sufficient work for each Story, technical assumptions marked | semantic |
| G08 Dependency Integrity | valid edges, no prohibited cycles, declared readiness without contradictions and agreed by the reviewer | mixed |
| G09 Scope Integrity | unsupported claims, exclusions, conflicts | semantic |
| G10 Planning Integrity | capacity, dates, units, no invented assignments; computed on a plan (`pbd plan`), NOT_APPLICABLE on a generation run | mixed |
| G11 Artifact Integrity | deterministic rendering, manifest/hash, counts, safe HTML | deterministic |
| G12 Publication Safety | verified target, plan hash, permissions, revisions and approvals | deterministic/mixed |
| G13 Independent Review | separate source-first review and disposition reconciliation | semantic |

INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable. Record reason per dimension; no arbitrary score threshold. A source coverage denominator cannot be derived solely from generated claims; use independent inventory and benchmark gold. Report raw counts and uncertainty. Do not mark missing semantic review as passed. Critical unresolved conflicts block affected publication. Review source obligations, every work item and every acceptance criterion individually, with explicit coverage and rationale.

See [benchmark protocol](../benchmarks/README.md).

## Readiness and blocking questions (schema 1.2.0)
Confirmed by a source, approved by the reviewer and ready to build are different facts. Each buildable item (story, enabler, spike, bug, task) carries an agent-judged `readiness` (`ready`, `partial`, `blocked`, `deferred`, `unassessed`) with a rationale and typed links: `blocked_by` cites the open blocking question (or item/relation) it waits for; `independent_of` names a blocking question that touches the item without preventing it, with why (a bounded spike, a mock contract). The runtime rejects at design time and reports under **G08**: ready work blocked by an open blocking question; a blocking question that blocks nothing; work a blocking question affects without either link; blockers already answered or withdrawn (stale); a ready parent with blocked or deferred children (use `partial`); ready work that waits for blocked work through a **confirmed** predecessor relation (hierarchy alone never propagates). The independent reviewer agrees or disputes each declared readiness (`readiness_check`); a dispute fails G08. Planning never places blocked or deferred work in a sprint. Backlogs written before 1.2.0 have no readiness: they show as *not assessed*, never as ready, and keep validating.

G05 uses [story engineering rubric](story-engineering.md); G06 uses [acceptance engineering rubric](acceptance-engineering.md); G07/G10 use [planning guidance](planning-engineering.md). Lexical warnings are not confirmed semantic violations. Include reviewer disposition and source locator for each item and criterion. See [targeted evaluation](../benchmarks/story-quality.md).

## Extended gates (stable IDs; original G01–G13 unchanged)
| Gate | Required evidence | Kind |
|---|---|---|
| G14 Semantic duplication | candidate pairs, independent rationale, justified exceptions | semantic |
| G15 Change safety | source version/supersession, preserved identity and human edits, revision preconditions | mixed |
| G16 Privacy and offline boundary | allowlist, no sensitive artifacts, no network during qualification | deterministic/mixed |
| G17 Target compatibility | discovered or mock schema, permitted types/fields/relations, explicit unavailable metadata | mixed |
| G18 Round-trip fidelity | compare exact expected/observed IDs, fields, HTML semantics and links; mock vs live separate | deterministic/mixed |

G12 remains authorization safety; G18 never passes for live publication from a mock. G11 covers local report fidelity. G13 remains independent review and must not be removed. See [evidence and health](evidence-and-backlog-health.md). Gate applicability depends on intent; a local generation run does not require tracker access. All live qualification is NOT_RUN until separately authorized.
