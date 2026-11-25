# Final integrated qualification protocol (pre-registered)

Registered and committed **before any run** of this phase. All cases, sources, baselines and gold are synthetic and invented for this repository. Original M1 results stay as recorded in `benchmarks/runs/m1`; results here belong to the frozen candidate only.

## Candidate
- Runtime frozen at the commit that registers this protocol (no runtime change since `b16d1a7`), installed from a wheel into a dedicated virtual environment outside the repository; the skill installed with `pbd skill install` into each sandbox.
- Sandboxes contain only `sources/` (and `baseline/` for audit). Gold is never named in generation or review prompts. As in M1, blindness is enforced by scoping and instructions, not by OS access control (disclosed limitation).

## Budget and models (owner policy)
- Economy first: Haiku-class for evaluation, Sonnet-class for generation and independent review; no Opus. At most 2 agents running at once.
- Roles per case: **generator** (one agent; it writes one reader ledger per declared source as separate logical readers, reconciles claims and designs), **independent reviewer** (a different agent, re-reads the sources first), **evaluator** (a different agent with gold, outputs and no transcripts). The coordinator only runs deterministic commands (`pbd start`, `pbd finalize`) and relays paths. This uses fewer physical agents per case than M1 (readers are not separate processes); it is recorded per run.
- Actual models are recorded as requested and as reported by each agent. Token counts are recorded only when the host reports them.

## Runs
| Id | What | Required |
|---|---|---|
| F1 | **New-session dogfood (QL-007):** a fresh agent with only the installed skill and ONE natural-language request on holdout `h1-vet-vaccines` (single PRD). The agent must run the whole flow itself (no coordinator commands). If it cannot start sub-agents, roles run sequentially and G13 is expected BLOCKED (documented fallback). | yes |
| F2 | **M1 regression, affected cases** under the frozen candidate: c04 and c06 (missed thresholds, QL-010), c02 and c05 (QL-001), c08 (QL-004), c12 (QL-005). | yes |
| F3 | **Audit holdout** `a1-canteen-audit` (QL-013): generator reads/reconciles, independent auditor audits the imported baseline. | yes |
| F4 | Remaining M1 cases (c01, c03, c07, c09, c10, c11). | only if budget remains; otherwise recorded NOT_RUN |

Planning, evolution, mock publication and the FTD handoff (QL-016) are exercised on F1's output by the coordinator with the deterministic CLI; their semantic agent-led use stays recorded as not qualified unless a run exercises it.

## Native-first (added before any run)
Readers follow the native-first procedure: originals first, declared reading method/tool/limitations per member. Evaluators additionally check that no PDF/image member is certified `read` from extracted text alone and that transcription-only evidence is labelled (QL-017).

## Thresholds (unchanged from M1 for F2; fixed here for F1 and F3)
- F1/F2: critical gold recall ≥ 0.90 per case (covered, or correctly question/conflict/blocked where gold expects it); zero critical trap violations; no gate PASS without verified evidence; c06 no active work on a superseded rule.
- F1 also: the run completes from one request with `report.html` produced, without the user chaining commands.
- F3: all 3 critical planted defects detected as findings; at least 3 of 4 planted defects detected; zero divergence findings on the 2 correct items.
- Failures are reported as failures. Thresholds are not changed after seeing results. One focused correction round is allowed for relevant failures, followed by re-running only the affected cases.
