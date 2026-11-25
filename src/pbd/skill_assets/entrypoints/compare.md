# /pbd-compare

Compare two existing backlogs against the same selected authorities. Follow [SKILL](../SKILL.md), [orchestrator procedure](../procedures/orchestrator.md) and the compare section of the [reviewer procedure](../procedures/reviewer.md).

```text
pbd start --mode compare --baseline left.json --baseline right.csv [--type-map map.json] --workspace <root> --source "prd.md=functional" --out <artifact-root>
```
- Both baselines are local files (PBD `backlog.json`, `pbd.import` JSON or CSV; a generated run's `output/backlog.json` is a valid side). Keys are namespaced `L-...` and `R-...`.
- Reading and claims run once; accepting the claims compiles both baselines. The comparer submits `pbd submit comparison`; `pbd finalize` writes `output/comparison.json`, `comparison.md` and `report.html`.
- Coverage of both sides uses the same independent inventory as denominator. Mappings are many-to-many with relation and rationale; unmatched and unsupported entries are derived. No winner, score or effort saving is computed; quality gates apply to one backlog, so audit each side for its gates.
