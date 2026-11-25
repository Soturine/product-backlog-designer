# /pbd-plan

`pbd plan --backlog backlog.json [--input planning.json] --out plan/` proposes an order and, only when a capacity is given, a sprint allocation. Outputs: `sprint-plan.json`, `sprint-plan.md`, `plan-report.html`. Everything is a proposal (`committed: false`).

Planning input (all optional, supplied or confirmed by the user — never guessed):
```json
{"capacity": {"unit": "story_points", "per_sprint": 20, "sprints": 4},
 "calendar": {"start": "2027-01-04", "sprint_days": 14},
 "technique": "wsjf",
 "technique_inputs": {"<item id>": {"moscow": "must"}},
 "teams": {"<item id>": "team-a"},
 "use_proposed_estimates": false,
 "scenarios": [{"name": "lower capacity", "per_sprint": 15}]}
```
- Only confirmed field values count; proposed estimates only with `use_proposed_estimates`, labelled. Zero is an estimate; absence is unknown. Points and hours are never converted.
- No capacity → a dependency-safe sequence, no sprints. No calendar → no dates. A calendar without capacity is refused.
- WSJF needs business value, time criticality, risk reduction and job size; RICE needs reach, impact, confidence and effort; MoSCoW needs the user's category. Missing inputs are listed per item; no score is invented.
- Checks: dependency cycles, invalid relations, external blockers, cross-team dependencies, unknown and zero estimates, items larger than a sprint (split needed).
- `pbd plan check --backlog backlog.json --plan plan/sprint-plan.json` exits 1 when the backlog changed after the plan (stale).
