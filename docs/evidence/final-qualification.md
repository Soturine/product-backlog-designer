# Final integrated qualification — results

Run 2026-11-25 under the [pre-registered protocol](../../benchmarks/final-qualification-protocol.md). Candidate runtime: `c93b2c5` (native-first reading + boundary fixes), installed from a wheel into a dedicated environment; the c08 correction re-run used `e8938d0`. All cases, sources and gold are synthetic; every artifact is in [benchmarks/runs/final](../../benchmarks/runs/final/) (outputs, independent reviews, gold evaluations, reading ledgers, per-agent log). Original M1 results in `benchmarks/runs/m1` are unchanged and are not attributed to this candidate. Nothing contacted a tracker.

## Roles, models, budget
- Per case: a **generator** (one agent: one logical reader per source as `sequential_role`, claims, design), an **independent reviewer** (a different agent, re-reads the sources first), a **blind evaluator** (a different agent with gold, outputs and no transcripts). The coordinator only ran `pbd start` / `pbd finalize` and relayed paths. Fewer physical agents per case than M1 (readers were not separate processes).
- Models actually used: generators and reviewers `claude-sonnet-5-5`; evaluators `claude-haiku-5-5`. No Opus. At most 2 agents at a time. 27 agent runs in total; per-agent tokens, tool calls and duration as reported by the host are in `agents-log.jsonl` (about 45k–110k tokens per agent).
- F1 ran as one fresh agent with only the installed skill and one natural-language request; it could not start sub-agents, so all its roles were sequential (G13 BLOCKED, as pre-registered).

## Results against the pre-registered thresholds
| Run | Case | Critical recall | Trap violations | Inventions (med/high) | Native-first | Gates not PASS | Threshold |
|---|---|---|---|---|---|---|---|
| F1 | h1-vet-vaccines (new session, one request) | 8/8 | 0/3 | 0/0 | ok (native) | G07 FAIL (story without tasks pending a blocking question), G13 BLOCKED (sequential), G18 NOT_RUN | **met**; report produced from one request |
| F2 | c04-code-tech | 8/8 (M1: 7/8) | 0/2 | 0/0 | ok | G02 FAIL, G07 FAIL (reviewer: 2 partial obligations, missing tasks), G18 NOT_RUN | **met** (QL-010) |
| F2 | c06-adr-supersession | 6/6 | 0/2 (M1: 1 violation) | 1/0 (FIFO order, caught by reviewer → G09 FAIL) | ok | G09 FAIL, G18 NOT_RUN | **met** (QL-010) |
| F2 | c02-multi-source | 10/10 | 0/2 | 1/0 | ok | G02 FAIL, G09 FAIL, G18 NOT_RUN | **met** |
| F2 | c05-contradictions | 8/8 (conflicts kept open) | 0/2 | 0/0 | ok | G18 NOT_RUN | **met** |
| F2 | c08-insufficient-tech | 4/4 counting question handling (3/4 strict) | 0/2 | 0/0 | ok | G07 FAIL, G18 NOT_RUN | **met**, but 7 unresolvable criterion references in task texts (QL-004 not fixed) |
| F2 correction | c08 re-run on `e8938d0` | 3/4 (gateway: question raised but integration task still ready to build → partial) | 0/2 | 2/0 | ok | G09 FAIL, G18 NOT_RUN | **missed** (0.75 < 0.90); item/criterion texts now have 0 broken references |
| F2 | c12-xlsx-source | 6/6 | 0/3 | 0/0 | ok (host cannot open .xlsx: declared extracted_text fallback with 5 limitations) | G18 NOT_RUN | **met** (QL-005: priorities confirmed) |
| F3 | a1-canteen-audit (audit holdout) | defects 4/4, critical 3/3 | — | — | ok | G02, G04, G05, G06, G09 FAIL (the planted defects), G07, G18 NOT_RUN | **met**: 0 false positives on the 2 correct items |
| F4 | c01, c03, c07, c09, c10, c11 | — | — | — | — | — | **NOT_RUN** (economy; not inferred) |

No gate passed without verified evidence (runtime-enforced). Where the independent reviewer and the evaluator differed (c04: two obligations partial for the reviewer, covered for the evaluator), the gate keeps the reviewer's computed result.

## Downstream modes on agent output (deterministic CLI, QL-016)
On F1's backlog: `pbd check` pass; `pbd plan` produced a 14-item dependency-safe sequence and no sprints (no capacity given); `pbd handoff ftd` 12 seeds and 2 open questions; local Azure package → mock prepare (21 CREATE) → approve → apply → verify **MOCK_VERIFIED**. No agent-led planning, evolution, comparison or refinement run was performed (QL-013/QL-016 remain open for those).

## Defects found and corrected in this qualification
- QL-004 was not closed by the visible-ID check: task texts cited criterion design keys. Fixed (`e8938d0`); the re-run shows 0 broken references in item/criterion texts. Reviewer finding prose may still cite item keys or a visible ID without its story (evaluator counted 10 in the re-run); recorded as residual.
- Agents on Windows wrote payloads in cp1252 (3 occurrences) → actionable error and UTF-8 guidance (`ce0536b`, QL-018).
- G18 reason was stale ("belongs to M3") → corrected.

## Not proven
- c08 re-run missed the recall threshold; run-to-run variation on the same case is real and is reported, not averaged away.
- G13 independence relies on separate agents in the same host; isolation is by scoping and instructions, not OS access control.
- Native PDF/image reading by an agent was not exercised (c11/c10 not run; QL-009, QL-017 partially open).
- Compare and refine were not run agent-led; planning, evolution and publication only deterministically on agent output.
- Accessibility scanner, other hosts, Linux symlinks: see the ledger (QL-008, QL-011, QL-015).
- Live Azure DevOps: NOT_RUN by design.
