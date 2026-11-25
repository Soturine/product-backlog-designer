# /pbd-audit

Audit an existing backlog against the selected authorities. Follow [SKILL](../SKILL.md), [orchestrator procedure](../procedures/orchestrator.md) and [reviewer procedure](../procedures/reviewer.md).

Inputs: functional authority (and optional technical/decision sources) as `--source`, and the existing backlog as a **local file** in the workspace: a PBD `backlog.json`, a `pbd.import` JSON (`{"kind": "pbd.import", "items": [{"id", "type", "title", "parent", "description", "acceptance_criteria", "fields"}]}`) or a CSV with `id,type,title,parent[,description,acceptance_criteria,...]`. Never fetch a backlog from a tracker.

```text
pbd start --mode audit --baseline backlog.csv [--type-map map.json] --workspace <root> --source "prd.md=functional" --out <artifact-root>
```
- Unknown work-item types refuse the run unless `--type-map` maps them (`{"Initiative": "epic"}`); nothing is guessed.
- The baseline is imported verbatim (`stages/baseline.json`): raw description and acceptance text, native IDs, field values as `proposed`. Acceptance HTML lists, tables, Gherkin scenarios and lines become individual criteria.
- Reading and claims run as in generation. Accepting the claims compiles the baseline as the design stage; there is no design submission.
- The independent reviewer audits every source obligation, item and criterion of the baseline (keys come from the work order, e.g. `I101`, `I101.AC2`). Gaps, divergences, superseded behavior still required and unsupported items are findings with expected/actual/why/impact/recommendation. Do not silently correct the baseline: audit is read-only.
- `pbd finalize` computes gates over the baseline as it is; failing gates are the audit result, not a pipeline error.
- Imported work carries no claim references, so G15 cannot detect a baseline criterion that still demands superseded behaviour; the reviewer must record it as a finding.
