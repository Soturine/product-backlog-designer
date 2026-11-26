# Corrective-round qualification protocol (pre-registered)

Registered and committed **before any run** of this phase. This is a new, bounded corrective phase after the final integrated qualification (`docs/evidence/final-qualification.md`, runs in `benchmarks/runs/final`). It does not alter, re-score or relax any earlier protocol, gold or result: those stay as recorded. Results here belong to the candidate named below only.

## Candidate
- Runtime: the commit that records this protocol (schema 1.2.0 readiness, team planning, report review controls; checkpoints `2739b37`, `5d4329f`, `5e248d3`), installed from a wheel into a dedicated virtual environment outside the repository; the skill installed with `pbd skill install` into each sandbox.
- Deterministic baseline passed on this candidate before any run (full pytest incl. browser tests, ruff, mypy strict, privacy scan; mutation catalogue run recorded in the evidence).

## Frozen inputs (SHA-256 of the LF-normalized files as committed)
| Case | File | Digest |
|---|---|---|
| c08 | `cases/c08-insufficient-tech/sources/prd.md` | `1f2b0ae20434a0f0581e988c73e8eda3697b10c95ef63e3162876cc266c84791` |
| c08 | `gold/c08-insufficient-tech.json` (unchanged since M1) | `e645df09cec64964d32a6746d3937d45daa98a244dca4e568d1ed3e700d7a566` |
| h2 (new holdout) | `cases/h2-court-booking/sources/prd.md` | `a15a16334fe3e33762ae0d89e03fbea9f041267e82aa3881c4847ac5a5301fd9` |
| h2 | `gold/h2-court-booking.json` | `7406c0454f9e7ddfab5a39a4c8c4f01a9debbab8eefc1344d1f48d3646a32674` |
| h2 R3 | `cases/h2-court-booking/baselines/left.json` | `e07713b075830baf24cc836458ec25babe52b3b0001cead67cf1bbc783c14b78` |
| h2 R3 | `cases/h2-court-booking/baselines/right.json` | `3e1c292e3cc2d889be6006917f22eaa4ef5f1019ab463bc8f67bb06a757590dd` |
| h2 R3 | `gold/h2-compare.json` (planted asymmetric defects, controls, expected mappings) | `a431c6722552d29dc9797e5a427c2093dc6c5244039bbd775431df2871e6bb58` |
| h2 R4 | `cases/h2-court-booking/v2/prd.md` (source change: the board decides the cancellation notice) | `9fa4946e90682ee44f130688cf8c1b16cb5b267e2d092d2008159a4a1c25e0c5` |
| c03 | `cases/c03-tables-annexes/sources/anexos/validacoes.docx` | `4d756a3afc1f7f0eea1e21dced5d254f059d089288f0104642512abe7f185750` |
| c10 | `cases/c10-incomplete-source/sources/fontes/fluxo-pedido.png` | `aa0e117003c3d63bab1210c06b1e5fd5979134b6f545eea92f6a4004234a357c` |
| c11 | `cases/c11-pdf-source/sources/prd.pdf` | `dd7bd2b767ba65e425851d461c290a567cca0248f39d9c5efff09c6cd73dde1c` |

The h2 holdout (different domain from c08: club court booking with an undocumented turnstile vendor API) and its gold were written by the coordinator before any run of this phase; the evaluator is a separate agent, but gold authorship is not independent of the coordinator (disclosed limitation). If a fixture defect is found, the original is kept and any revision is qualified separately.

## Budget and models
Sonnet-class for generation and independent review, Haiku-class for blind evaluation, no Opus, at most two agents running at once. Generators get only the installed skill, `sources/` and the request; reviewers get the run directory and sources; gold is given only to evaluators. Blindness is enforced by scoping and instructions, not OS permissions. Actual model identifiers and host-reported usage are recorded; nothing is estimated.

## Runs
| Id | What | Sample | Closes if |
|---|---|---|---|
| R1 | c08 blocking-readiness regression (QL-019): generator → separate reviewer → evaluator | **3 independent runs** | every run meets the thresholds below |
| R2 | h2 holdout, same roles | 1 run | thresholds below |
| R3 | Agent-led compare + refine on synthetic baselines (QL-013), one agent from one natural-language request | 1 run | common inventory, side-specific dispositions, many-to-many mappings, no winner; refine applies only approved targeted changes |
| R4+R5 | Agent-led planning on the R2 backlog (two one-week sprints, two developers, one owner per story, estimates stated in the request), evolution after the v2 source change (the board answers the cancellation question), local package + mock publish/verify, from natural-language requests (QL-016) | 1 run | plan passes runtime checks with blocked work unallocated; evolution preserves identities; mock read-back verified; no live call |
| R6 | Native reading of DOCX (c03), PNG (c10) and PDF (c11) originals, reading stage only (QL-017, QL-009) | 1 run | each member declares its actual method and limitations; no PDF/image certified `read` from extracted text alone |
| R7 | Real Functional Test Designer consumption of the R2 handoff | 1 run | FTD's own workflow produces Test Cases traced to the handoff; generated ≠ executed |
| R8 | Fresh installed skill on a second host (Codex CLI) with one natural-language request on h2 | 1 run | report produced; independence recorded honestly; explicit invocation is not called automatic discovery (QL-015) |

F4 full generation of c01, c03, c07, c09, c10, c11 is **not run** in this phase (budget); R6 exercises only the reading of the c03/c10/c11 originals. Unrun cases are recorded NOT_RUN with that reason.

## Thresholds (R1, R2)
- Critical gold recall ≥ 0.90 **per run** (covered, or handled as question/blocked where gold expects it); strict coverage and correctly handled non-coverage reported separately; no averaging across runs.
- Zero critical trap violations.
- Readiness (added for this phase, judged by the evaluator against the gold's own expectations, not by changing gold): work that needs the unanswered gateway/turnstile decision is not presented as ready (it is blocked, deferred, or the decision is isolated in a bounded spike/question with the implementation not ready); unrelated work is not blocked by association.
- No unresolved reference in structured references or user-facing prose (item/criterion text, reviewer notes and findings).
- Medium or high inventions are reported; more than 2 medium or any high invention fails the run.
- A threshold pass never turns a gate FAIL into PASS; gate states are reported as computed.

## Correction policy
At most one targeted fix and re-qualification cycle for a genuine new defect; initial runs are preserved and reported. No re-running until a run passes.

## Correction cycle (recorded after R1a–c, R2 and R6; before any other run)
Two genuine runtime defects were found by the runs on `c9c5634`; the initial runs are preserved unchanged and evaluated as recorded.
- **D1** (R1c and R2 independently): a `partial` item could not cite the blocking question in `blocked_by`, which pushed one agent to describe a partly blocked story as independent of its blocker and another to drop the story from the question's `affects`. Fix: only `ready` contradicts an open blocker; a `partial` item cites the question that blocks its remaining part.
- **D3** (R6): on a host without the optional `pypdf` extra, a PDF the agent had read natively (rendered pages) was refused as unreadable. Fix: a PDF without an extractable text layer is a visual member, certified only through native vision with a recorded transcription; quotes are agent transcriptions, never mechanical.
The remaining runs (R3, R4+R5, R7, R8) and the targeted requalification (R2b on h2, R6b on the PDF) run on the commit that records this section. No threshold, case or gold changes.
