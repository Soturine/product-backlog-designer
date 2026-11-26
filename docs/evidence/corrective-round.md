# Corrective round — qualification results

Run 2026-11-25/26 under the [pre-registered corrective protocol](../../benchmarks/corrective-qualification-protocol.md). This is a bounded corrective phase after the [final integrated qualification](final-qualification.md); earlier results, gold and protocols are unchanged. All cases, sources, baselines and gold are synthetic. Artifacts: [benchmarks/runs/corrective](../../benchmarks/runs/corrective/) (outputs, reviews, reading ledgers, evaluations, exact role prompts in `prompts.md`, per-agent usage in `agents-log.jsonl`, tool reports in `tooling/`). Nothing contacted Azure DevOps, Jira or any tracker.

## Candidates actually tested
| SHA | Role |
|---|---|
| `c9c5634` | frozen candidate for R1a–c, R2, R6 (readiness contract, report review tool, team planning) |
| `9cfb3c4` | first correction cycle (D1 partial blockers, D3 native PDF): R2b, R3, R4+R5, R6b, R7 handoff, R8 |
| `f512dea` | second correction cycle (D4–D8, disclosed deviation): R4b |
| `68a83a8` | final code candidate (D9, accessibility fixes): full deterministic qualification |

Each run used a wheel built from its candidate and installed in a dedicated virtual environment outside the repository (no optional `pypdf` extra); the skill was installed with `pbd skill install` into each sandbox.

## Roles and models
Generators, independent reviewers and single-agent workflow runs: `claude-sonnet-5-5`. Blind evaluators: `claude-haiku-5-5`. No Opus; at most two agents at a time. R8 ran on Codex CLI 0.170.0 (session model `gpt-5.6-sol`; its role payloads self-reported `gpt-5`, so the exact role models are unverified). Isolation is by scoping and instructions, not OS permissions. Gold was given only to evaluators; the h2 gold was written by the coordinator (not independent of it).

## Semantic runs
| Run | Case / what | Critical (handled / strict) | Traps | Readiness (dependent work not ready, unrelated not blocked, blocker linked) | Inventions med/high | Gates not PASS | Verdict |
|---|---|---|---|---|---|---|---|
| R1a | c08 | 4/4 (3) | 0/2 | yes / yes / yes | 1/0 | G02, G09 FAIL; G18 NOT_RUN | met |
| R1b | c08 | 4/4 (3) | 0/2 | yes / yes / yes | 1/0 | G04, G09 FAIL; G18 NOT_RUN | met |
| R1c | c08 | 4/4 (3) | 0/2 | yes / yes / yes (one borderline: a state-rule task ready against a simulated signal) | 1/0 | G02 FAIL; G18 NOT_RUN | met |
| R2 | h2 holdout (new domain) | 5/5 (4) | 0/3 | yes / yes / yes | 0/0 | **G08 FAIL** (reviewer disputes readiness of the booking story/task over the 22h boundary), G02/G17 BLOCKED, G18 NOT_RUN | met |
| R2b | h2 after D1 fix | 5/5 (3) | 0/3 | yes / yes / yes | 2/0 | G02, G04, **G08**, G09 FAIL; G17 BLOCKED; G18 NOT_RUN | met (2 medium = limit) |
| R8 | h2 on Codex CLI, one request | 5/5 (3) | 0/3 | yes / yes / yes (cancel story over-blocked, low) | 0/0 | G17 BLOCKED; G18 NOT_RUN | report produced; see limits |
| R3 | compare + refine (h2 baselines) | planted 5/5 on the correct side; 0 false positives on 2 controls; mappings 2 exact + 1 partial; no winner | — | — | — | compare mode | met; refine not exercised (the approved change already existed) |
| R4+R5 | plan + evolve + package on R2 backlog | plan G10 BLOCKED (unknown estimates, no violations), blocked story unallocated, no invented QA tasks; evolution kept identities, 0 deletions, stale plan flagged | — | — | — | — | partially met: exposed D4–D8; mock publication not reached |
| R4b | evolve + real refine + package + mock on R2b backlog (`f512dea`) | question answered by the approved decision, blocked task → ready, partial story → ready, 17 IDs kept, 0 deletions; one approved title change applied, nothing else; 17 CREATE → approve → 17 APPLIED → **MOCK_VERIFIED** | — | — | — | evolved/refined backlog not re-reviewed (gates invalidated) | met |
| R6 | reading only: c03 DOCX, c10 PNG, c11 PDF (`c9c5634`) | PNG read natively (no obligations: unlabeled boxes); DOCX: host refuses binary originals → declared `extracted_text` fallback, 7 obligations; PDF read natively but refused by the runtime → **D3** | — | — | — | — | defect found |
| R6b | reading only: c11 PDF after D3 | PDF classified visual, read with `native_vision` + transcription, 7/7 critical gold obligations at reading stage, page 3 not invented, table values kept (coordinator check; no full c11 generation) | 0/2 | — | — | — | met (reading stage only) |
| R7 | real Functional Test Designer v2.5.0 (`314e8d6`) on the R2b handoff | FTD run `ftd-r7`: 8/8 FTD gates, `verify: true`; 48 Test Cases designed (14 acceptance, 19 derived, 13 exploratory, 2 E2E; 2 BLOCKED_EXTERNAL_DEPENDENCY); 17 seed/guidance dispositions (9 already covered, 5 materialized, 1 question, 1 ordering, 1 n/a); 3 PBD questions carried, 7 new | — | — | — | — | met; **designed, not executed**; FTD outputs carry no PBD IDs (link only via seed anchors) |

Thresholds: critical ≥ 0.90 per run counting covered or correctly handled-as-question/blocked where gold says the information is unknown, zero critical trap violations, readiness as above, ≤ 2 medium and no high inventions. Strict coverage is reported separately. A threshold pass never turns a gate FAIL into PASS.

## Defects found by the runs and fixed
| Id | Found by | Defect | Fix | Requalified |
|---|---|---|---|---|
| D1 | R1c, R2 | a `partial` item could not cite its blocker; one agent declared a partly blocked story "independent", another removed it from the question's `affects` | only `ready` contradicts an open blocker | R2b (no readiness rejection) + tests |
| D3 | R6 | PDF read natively but refused without the `pypdf` extra | text-less PDFs are visual members (native vision + transcription) | R6b + tests |
| D4 | R4 | no way to answer a question with a decision and recompute readiness | `answer_question`, `set_readiness` evolution ops | R4b + tests + mutant |
| D5 | R4 | `set_field` accepted an unknown name (`readiness`) | unknown field names refused | tests + mutant |
| D6 | R4 | blocked task inherited its story's sprint | blocked/deferred tasks unallocated | tests + mutant |
| D7 | R4 | plan summary/Markdown ignored the team plan | included | tests |
| D8 | R4 | no package from an existing/evolved backlog | `pbd azure package` | R4b + tests |
| D9 | R4b | `azure snapshot` output not accepted by `prepare` | normalized snapshots accepted with digest check | tests only |
The protocol pre-registered one correction cycle; the second (D4–D9) is a disclosed deviation. Runs that found defects are preserved unchanged.

## Recurring semantic limitation (not fixed by rules)
In both h2 generations (R2, R2b) the designer marked the question "does the last block start or end at 22h?" non-blocking and the booking story/task ready; both independent reviewers disputed it and G08 failed. The R8 run on Codex classified differently. Classifying whether a question blocks work is an agent judgment; the runtime does not and must not hard-code domain rules. The reviewer's `readiness_check` surfaced the disagreement every time, so it is visible, not hidden — but generator variance on this judgment is real (ledger QL-020).

## Comparison with a bare agent (one case, same model)
A bare Sonnet agent (no skill, same PRD and request, 48k tokens, 57 s) was scored by a separate blind evaluator with the same rubric and gold: see `benchmarks/runs/corrective/eval/bare.json` and the summary below. Upstream tools (Spec Kit, BMAD, HVE Core, OpenSpec) were **not** run; no superiority claim is made from one case.

| | PBD h2 generations (R2, R2b, R8) | Bare agent |
|---|---|---|
| Critical handled (strict) | 5/5 (4, 3, 3) | 5/5 (4) |
| Trap violations | 0/3 each | 0/3 |
| Readiness (dependent not ready, unrelated not blocked) | yes | yes (cancel blocked at story level while its tasks are ready) |
| Inventions medium/high | 0/0, 2/0, 0/0 | 1/0 (+6 low) |
| Source quotes and locators, independent review record, machine-checked invariants and gates, offline report | yes | no |
| Tokens (host-reported) | ~140k generator + reviewer per run | 48k |

On this small, clear PRD the bare agent was as good on the gold and cheaper; PBD's measured difference here is verifiability (traceability, independent review, invariants, gates, report), not better coverage. One case is not a benchmark.

## Deterministic qualification of the final candidate `68a83a8`
`python tools/qualify.py --mutation --playwright` with `PBD_AXE_JS` set (Windows 11, Python 3.11.18, system Edge), summary in `benchmarks/runs/corrective/tooling/qualify-68a83a8.json`:
- ruff check and format: pass (166 files); mypy strict: pass (63 source files).
- pytest with branch coverage: **495 passed, 2 skipped** (Windows symlink privilege, QL-008), including Playwright browser tests and both axe scans; coverage **89%** of `src/pbd` (branch).
- Privacy scan: 0 findings. Mutation catalogue: **33/33 killed** (20 earlier + 13 for this round: blocked-as-ready, blocking question blocking nothing, blocked work scheduled, reviewer dispute ignored, delegation shown as actual, unknown estimate as zero, over-capacity accepted, task points added to the story, visible criterion IDs in reviewer prose, unescaped unknown icon type, unapproved decision answering a question, unknown field accepted, blocked task following its story). The catalogue is a targeted set, not a mutation score.
- Packaging: wheel built from the candidate and installed in a fresh virtual environment outside the checkout; `pbd --version` reports schema 1.2.0, `pbd doctor` offline, `pbd skill install` writes SKILL.md, procedures, entrypoints and docs; the wheel carries icons, CSS, locales, schemas and skill assets (124 files). The sdist was not rebuilt this round.
- Old artifacts: the recorded final and M1 runs re-render with the new renderer (readiness shown as not assessed) without any change to the recorded files; the M1 re-renders were refreshed.

## Quality tools on the candidate (static, read-only)
- **Assertiva 1.0.0** (`d4d8d49`), `assertiva audit` on a clean export: 3 MEDIUM (no CI pytest — PBD qualifies locally by owner policy; one security test without an assertion — **fixed**; 15 error tests not asserting the error field — recorded), 2 INFO (state after rejection not checked in 31 tests; no delivery pipeline). It did not execute tests, measure coverage, mutation or packaging (its own "not evidenced" list).
- **Derivanta Engine 0.1.0** (`acd6ca3`, checkout on a docs branch, framework `218761d`), `inspect --maintainability`, read-only, no code execution: 143 INFO hypotheses (69 complexity, 64 duplication, 10 unreferenced), no defect-level finding. Largest refactoring drivers: `compute_gates` (96 decision paths) and `_team_plan` (95) — recorded as maintainability debt (QL-022).
- **axe-core 4.10.2** (local test tooling, never shipped): 82 violation groups before (contrast of the faint token, links by color only, unfocusable scroll containers, small targets) → 0 after on every view of five example reports, light/dark, 1280/390 px. `tests/e2e/test_report_axe.py` repeats it when `PBD_AXE_JS` is set (skipped otherwise); runs use reduced motion because mid-animation opacity produced transient contrast failures. This is an automated scan, not a WCAG conformance claim: manual screen-reader review was not performed.

## Performance (same fixture, host and browser; 5 samples, medians)
| | `4842db2` | candidate | budget |
|---|---|---|---|
| HTML | 5.62 MB | 6.57 MB | < 7 MB |
| render | 0.225 s | 0.256 s | < 3 s |
| browser load | 843 ms | 866 ms | < 6 s |
| filter | 5.1 ms | 5.8 ms | < 300 ms |
Size headroom is now 0.43 MB (type icons per row); recorded as a limitation.

## Not proven / not run
- Live Azure DevOps or Jira: NOT_RUN by design; G18 never passes from a mock. Jira has an appearance only, no mapping or export.
- F4 full generation of c01, c03, c07, c09, c10, c11: NOT_RUN (budget); only the reading of c03/c10/c11 originals ran (R6/R6b).
- DOCX/XLSX native reading: the Claude Code host refuses binary originals; readers declare an extracted-text fallback (QL-017 partly open).
- Automatic skill discovery on Codex: not proven (R8 named the skill path); Linux symlink tests: not run (QL-008).
- Manual accessibility review (screen reader, full keyboard walkthrough): not performed (QL-011 open).
- FTD Test Cases were designed, not executed; FTD outputs do not carry PBD IDs (QL-021).
- Upstream comparative benchmarks: not run.
