# /pbd-refine

Selective local refinement of a canonical backlog (`backlog.json`). Follow [SKILL](../SKILL.md) and [designer procedure](../procedures/designer.md).

1. Write a proposal with targeted changes and a rationale each:
```json
{"author": {"agent": "refiner-1", "model": "<actual model>"},
 "changes": [{"key": "R1", "op": "update_title", "target": "<PBD item id>", "value": "...", "rationale": "..."},
   {"key": "R2", "op": "add_criterion", "target": "<item id>", "expected_outcomes": ["..."], "claim_refs": ["<claim id>"], "rationale": "..."},
   {"key": "R3", "op": "set_criterion_status", "target": "<criterion id>", "status": "superseded", "rationale": "..."},
   {"key": "R4", "op": "set_field", "target": "<item id>", "field": "priority", "state": "confirmed", "value": 1, "claim_refs": ["<claim id>"], "rationale": "..."}]}
```
Operations: `update_title`, `update_description`, `set_field`, `add_criterion`, `update_criterion`, `set_criterion_status`, `add_item`, `move_item`. There is no delete: retire a criterion with `superseded`/`out_of_scope`. Assignments, dates and effort fields are refused; a confirmed value or criterion needs claim references.
2. `pbd refine plan --backlog backlog.json --file proposal.json --out refine/` validates every change against the base and writes `refinement-plan.json` (before/after per change, base and plan digests) and `refinement-diff.md`. Nothing is applied.
3. Show the diff to the owner. Only after they choose: `pbd refine apply --backlog backlog.json --plan refine/refinement-plan.json --approve R1,R3 --plan-digest <digest> --out refine/`. A changed base backlog or plan is refused (conflict). Changed items return to `draft`; review, gates and derived plans/packages must be produced again.
