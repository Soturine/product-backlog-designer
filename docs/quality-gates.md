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
| G08 Dependency Integrity | valid edges and no prohibited cycles | mixed |
| G09 Scope Integrity | unsupported claims, exclusions, conflicts | semantic |
| G10 Planning Integrity | capacity, dates, units, no invented assignments | mixed |
| G11 Artifact Integrity | deterministic rendering, manifest/hash, counts, safe HTML | deterministic |
| G12 Publication Safety | verified target, plan hash, permissions, revisions and approvals | deterministic/mixed |
| G13 Independent Review | separate source-first review and disposition reconciliation | semantic |

INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable. Record reason per dimension; no arbitrary score threshold. A source coverage denominator cannot be derived solely from generated claims; use independent inventory and benchmark gold. Report raw counts and uncertainty. Do not mark missing semantic review as passed. Critical unresolved conflicts block affected publication. Review source obligations, every work item and every acceptance criterion individually, with explicit coverage and rationale.

See [benchmark protocol](../benchmarks/README.md).
