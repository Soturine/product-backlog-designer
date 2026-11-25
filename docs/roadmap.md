# Roadmap

Status: CP0/M0 met ([M0 evidence](evidence/M0.md)). CP1/M1 substantially complete ([M1 evidence](evidence/M1.md)): agent-led generation dogfooded on 12 synthetic cases with gold evaluation; open items are an end-to-end run in a new host session driven only by natural language and Linux symlink qualification; two pre-registered thresholds were missed (c04 critical recall, c06 trap). M2–M6 pending. Documentation does not count as runtime completion.

| Milestone | Deliverables | Exit evidence |
|---|---|---|
| M0 Foundation | constitution, canonical schemas, source allowlist, stable identity, state, CLI scaffold, profiles, gold fixtures | schema/identity/security tests, documented install, baseline manifest |
| M1 Generation | agent readers, claims, Epic/Feature/Story/AC/Task, dependencies, rich text, HTML/MD/JSON/CSV/XLSX, selective modes | real agent run on synthetic multi-source case, source recall and individual traceability review |
| M2 Audit & compare | independent review, INVEST, reverse coverage, gaps, conflicts, questions, profile learning, full report | mutation detection, blind comparison, per-item and per-criterion findings |
| M3 Azure | schema discovery, export, mapping, preview, approved apply, recovery, read-back | offline contract mocks, mock round-trip, idempotency and concurrent edit tests; separately authorized disposable live qualification remains NOT_RUN |
| M4 Planning | estimates, priorities, risk, capacity, iteration plans | missing-capacity refusal, dependency/capacity consistency, human review |
| M5 Evolution | ADR/diff, stable identity, lineage, reconciled updates | version-change fixture, no duplicate or destructive sync, stale approval rejected |
| M6 Ecosystem | FTD handoff, optional GitHub/Jira, agent portability, benchmark qualification | real independent agent evaluations, supported-adapter evidence, release review |

Prioritize M0–M3 for usable workflow. No release or maturity claim without exit evidence. Work in checkpoints with baseline, implementation, tests, evidence, review and explicit residual risks. Use Derivanta and Assertiva where compatible, recording actual executions; QE Engineering for strategy. CI budget policy: local qualification first, avoid unnecessary remote runs. No automatic public release or tag.

## Cross-cutting acceptance
All milestones maintain privacy, backward-compatible contracts or migration notes, documentation hyperlinks, changelog, test evidence and no fake metrics. Scope expansion requires explicit decisions. See [benchmark protocol](../benchmarks/README.md).

## Reuse and user experience checkpoints
M0: pinned upstream adoption decisions and license review, one-entrypoint intent router and canonical contract. M1: one-request end-to-end generation, default JSON + offline two-layer HTML, local Azure package contract and synthetic report tests. M2: full individual audit, not just aggregated findings; independent source review and UX tests. M3: approved CLI-friendly publication and remote read-back, manual CSV fallback with disclosed fidelity. M4–M6: incremental enhancements without increasing mandatory user interaction. See [upstream code audit](upstream-code-audit.md), [usage](usage.md), [reporting](reporting.md), [coverage crosswalk](coverage-crosswalk.md).

## Implementation directive
Execute [master directive](PBD_AGENT_LED_MASTER_DIRECTIVE.md) by checkpoint, starting at M0. See [agent-led execution](agent-led-execution.md) and [calibration](../benchmarks/calibration.md). No live tracker access during this implementation round. Generation without existing backlog is a mandatory M1 acceptance case. The original 13 gate IDs remain stable; extensions G14–G18 cover duplication, change safety, privacy, compatibility and round-trip.

## Git checkpoint policy
Every qualified checkpoint CP0–CP6 requires its own commit, push and remote verification under the owner's authorized Git identity, without AI co-author trailers or contributor entries. Use main only when permitted and consistent with CI budget; otherwise push development checkpoints and integrate into main through required checks. See [mandatory Git policy](PBD_AGENT_LED_MASTER_DIRECTIVE.md#git-checkpoint-and-authorship-policy-mandatory). No force pushes or tags/releases.
