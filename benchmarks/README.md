# Benchmark and evaluation protocol

Status: designed, not executed. Use synthetic or explicitly licensed public fixtures only. Never include corporate examples or snapshots.

## Baselines
Same model, budget, sources, instructions and environment where feasible: bare agent; HVE Core; BMAD; Spec Kit; Task Master AI; PBD; independent human-reviewed gold. Optional Azure Prototype and PRD-to-Jira where comparable. Pin commit/version, model, date, temperature if supported, tools, token budget, elapsed time and failures. Record adaptations and noncomparable features. Run multiple repetitions and separate development from holdout. Blind generation must not see reference backlog; independent reviewers should not know generator identity.

## Corpus
Small/large PRDs, multiple sources and directories, tables/diagrams, contradictory revisions, missing requirements, nonfunctional constraints, web/mobile/ERP/industrial-style synthetic cases, custom processes, existing backlogs, changes, multilingual Unicode, dependencies and failure recovery. Gold atomic claims and locators independently reviewed, plus acceptable alternative mappings; no fixed item count.

## Metrics
Requirement recall = matched gold / eligible gold; precision = supported extracted / extracted; semantic coverage = obligations adequately represented / eligible gold; acceptance completeness = covered expected behaviors / eligible expected behaviors; unsupported claims count/rate; hierarchy integrity; duplicate rate; conflict detection recall; finding precision; task sufficiency; traceability accuracy; publication fidelity; idempotency (second apply creates/updates zero); human rework/time; token use; elapsed time; run variance. Report numerator/denominator, exclusions, uncertainty, model and reviewer disagreement. Undefined denominator → N/A. No score solely from generated claim set.

## Mutations and regression
Remove gold obligation, drop criterion, invert rule, duplicate Story, orphan Task, cycle dependency, alter source locator, introduce unsupported behavior, stale revision, invalid custom field, wrong target, malicious HTML, CSV injection, Unicode corruption, lost response after create, retry and partial apply. Assert detection and no unsafe write. Test the evaluators themselves with known good/bad cases. Unit/property/contract/integration/security/regression/E2E suites; live sandbox results separate from mocks.

## Qualification
Report raw outputs and hashes, per-case metrics, reviewer rationale and disagreement, failures/skips and comparison limitations. Pre-register thresholds per benchmark before running; deterministic integrity and safe publication invariants must pass. No fabricated scores or claimed superiority. Use [Assertiva](https://github.com/Soturine/Assertiva) and [Derivanta](https://github.com/Soturine/derivanta) when compatible; record real versions and results. [Roadmap](../docs/roadmap.md).
