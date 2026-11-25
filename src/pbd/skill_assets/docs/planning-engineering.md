# Technical tasks and planning

## Tasks and dependencies
Start from accepted behavior and technical authority. For every story identify needed design, implementation, data, integration, migration, testing, documentation, operational readiness, deployment and security work only as applicable. Map each task to criteria/claims or a justified enabling need. Use concise action title, scope, result, verification, dependencies, activity and estimate provenance. Avoid generic “do frontend” and duplicate testing tasks. A spike has a research question, timebox (if supplied/approved), decision artifact and follow-up, not a commitment to implement an unknown solution. Do not assume a framework from the PRD alone. SMART is a review heuristic, not a required sentence format. Test tasks plan work; FTD owns Test Cases.

Dependencies: distinguish hierarchy, sequencing (predecessor/successor), related work and external blocker. Record reason, source, confidence and status; validate graph and flag cycles. Independent stories may still share a platform or legitimate sequencing. Never create fake dependency links.

## Prioritization and sizing
Keep ordinal priority distinct from ranking and numerical scores; discover destination semantics. MoSCoW requires agreed scope; RICE = reach × impact × confidence / effort with defined units and time horizon; WSJF requires agreed cost-of-delay components and relative job size. Do not calculate with invented inputs. Preserve rationale and sensitivity to uncertain inputs; don't compare incomparable scales. Story points are team-relative proposals, not hours. Feature effort and task estimates are distinct and not automatically additive. Never fill completed work/time logged. Teams own final estimates.

## Iteration planning
Use confirmed team, capacity, dates, availability, velocity where relevant, dependency order and release objectives. Produce suggested slices with Sprint Goal, selected items, capacity assumptions, blockers, carryover and unallocated work. Without necessary evidence return sequencing/options only, not committed sprint dates. No assigning people or moving items remotely without approved plan. Avoid maximizing utilization at the expense of risk and collaboration. Document DoR/DoD as team policies; do not infer completion.

## Audit
Review every task for scope, sufficiency, actionable result, activity and parent/criterion linkage. Review capacity and estimates separately from functional coverage. Findings distinguish absence, legitimate unknown and optional improvement. No automatic correction of human plans. See [work items](work-items.md), [sources](research-references.md).

## Implemented (M4)
The planning engine (`src/pbd/pipeline/planning.py`, `pbd plan`) implements the rules above for local backlogs: dependency-safe ordering, optional MoSCoW/RICE/WSJF with complete inputs only, sprint allocation only with a known capacity and matching unit, dates only from a user calendar, scenarios, cycles/blockers/cross-team checks and staleness against the backlog digest. See [/pbd-plan](../entrypoints/plan.md).
