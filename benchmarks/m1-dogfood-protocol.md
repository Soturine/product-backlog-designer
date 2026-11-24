# M1 agent-led dogfood protocol (pre-registered)

Registered before any generation run. Cases, sources and gold are entirely synthetic and invented for this repository.

## Cases
| Case | Challenge |
|---|---|
| c01-prd-only | a single PRD, no other source |
| c02-multi-source | PRD + rules directory + informative glossary (3 sources) |
| c03-tables-annexes | requirements in a Markdown table + validation table in a `.docx` annex |
| c04-code-tech | PRD + TDD + source code that contradicts the PRD (code is evidence, not authority) |
| c05-contradictions | two functional sources disagree twice |
| c06-adr-supersession | approved ADR supersedes a PRD rule; a proposed ADR must not |
| c07-negative-flows | negative, exception and offline flows (English) |
| c08-insufficient-tech | payment gateway without contract; vague performance requirement |
| c09-selective-levels | only stories and acceptance criteria requested |
| c10-incomplete-source | functional states defined only in an unreadable diagram |

## Isolation
- Each case runs in a sandbox copy that contains only `sources/` (outside the repository). Gold files are never given to generation or review agents; their prompts name only the sandbox paths.
- Roles per case: one reader subagent per declared source → one generator subagent (claims reconciliation + design) → one reviewer subagent that did not generate → finalize (runtime) → one evaluator subagent that receives gold and outputs but not the generator transcripts.
- The coordinator (who wrote the gold) only runs deterministic commands (`pbd start`, `pbd finalize`) and relays file paths. This is a disclosed limitation: blindness is enforced by scoping and instructions, not by OS-level access control.
- Actual models used per role are recorded from what each agent reports and what was requested.

## Measures (per case)
Gold recall (critical and all), invented requirements (items/criteria asserting behavior absent from sources and not marked proposed), trap violations, expected conflicts/supersessions/questions/unreadable members handled, level compliance, story quality and criteria observability (evaluator judgment with rationale), task actionability, traceability correctness (sampled locators), false positives in the reviewer's findings, gate outcomes.

## Pre-registered thresholds
- Critical gold recall ≥ 0.90 per case (COVERED or correctly QUESTION/CONFLICTING/BLOCKED where gold expects it).
- Zero critical trap violations (fabricated thresholds, silently resolved conflicts, active work on superseded rules, invented states).
- Level compliance 100 % for c09.
- c10: G01 must not PASS.
- No gate PASS without verified evidence (runtime-enforced).
Failures are reported as failures; thresholds are not changed after seeing results.
