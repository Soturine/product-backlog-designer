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
- Blocked or deferred work (declared readiness) is never placed in a sprint; it is listed as not planned with its blocker.
- Parent and child estimates are never added: points count on stories, hours on the leaves that carry them.

Team plans (only when the user supplies the team): the agent turns a request such as "two one-week sprints, two developers, one accountable developer per story" into a proposal; the runtime only checks it.
```json
{"team": [{"id": "dev-a", "skills": ["backend"], "capacity": {"unit": "hours", "per_sprint": 30}},
          {"id": "dev-b", "capacity": {"unit": "hours", "per_sprint": {"1": 30, "2": 20}}}],
 "sprints": [{"index": 1, "working_days": 5, "goal": "..."}, {"index": 2, "working_days": 5}],
 "responsibility": "story_owner",
 "proposal": {"placement": {"<story id>": 1, "<task id>": 1}, "owners": {"<story id>": "dev-a"},
              "assignees": {"<task id>": "dev-b"}, "rationale": {"<story id>": "why here"}},
 "actual": {"source": "snapshot.json", "assignees": {"<item id>": "dev-a"}},
 "assessments": {"<item id>": {"complexity": "high", "risk": "medium", "confidence": "medium", "rationale": "..."}}}
```
- `responsibility`: `story_owner` (one accountable owner per story; task assignees may differ and are shown as collaborators), `task_split`, or `whole_story_delegation` (tasks follow the owner, shown as *derived*, never as actual; a tracker does not change child assignments when a parent is assigned).
- Members, availability, skills and dates come from the user; never invent people, velocity or estimates. Tasks follow their story's sprint unless placed explicitly (earlier = preparation, later = carryover).
- Load is computed per person in that person's capacity unit only; unknown estimates and unit mismatches are listed, never counted as zero. Over-capacity, blocked placements, predecessors placed later and stories without the requested owner fail G10; unverifiable capacity is BLOCKED.
- Actual assignments come only from a supplied local snapshot (`actual`) and are shown beside the proposal.
- `pbd plan check --backlog backlog.json --plan plan/sprint-plan.json` exits 1 when the backlog changed after the plan (stale).
