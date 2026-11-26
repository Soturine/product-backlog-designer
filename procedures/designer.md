# Designer procedure

Design only the requested levels from `stages/claims.json`. Write every item from its own claims; templated text (same sentence with swapped names/numbers) is rejected. Use [story engineering](../docs/story-engineering.md), [acceptance engineering](../docs/acceptance-engineering.md) and [planning](../docs/planning-engineering.md).

## Engineering rules
- **Never reference a criterion in text** (neither its key such as `AC3` nor a visible ID such as `CA-02`): visible IDs restart per story and keys are not shown. Describe the behavior the task verifies; the runtime rejects such references.
- **Ambiguity is not a choice you make.** When a claim is ambiguous, conflicting or unknown, do not confirm one reading in a criterion, field or task: write the alternatives, keep the criterion `proposed` with a rationale, and raise a question with its impact. The runtime rejects confirmed criteria and fields that trace only unresolved claims.
- **Every effective obligation must be verifiable where it lives.** A value or rule written only in an Epic or Feature (a limit, a duration, a lockout) is not verifiable: carry it into a criterion, a verifiable rule of a story, or a task with a check. The runtime signals claims covered only by epics/features.
- **Superseded behavior is not work.** Do not create tasks to remove or migrate a superseded mechanism unless implementation evidence shows it exists; otherwise ask whether it exists.
- **Values stated by sources are confirmed fields.** A priority, estimate or category given by a source (for example a "Prioridade" column) is recorded as `state: confirmed` with the claim that carries it; never confirm values the sources do not state.
- **Epic** = outcome with scope boundaries; **Feature** = capability; **Story** = smallest valuable vertical slice for a real actor named in the sources (never invent an actor); **Enabler** = justified technical capability without persona; **Spike** = a specific question with decision output; **Task** = concrete work with expected result and verification.
- No fixed counts of anything. Detail follows real complexity. Split with SPIDR (paths, interfaces, data, rules, spikes) only when each slice stays valuable; never split by UI/API/DB layers.
- Acceptance: one observable outcome per criterion where practical, positive + negative + exceptions **that the sources support**. Use Example Mapping (rule → examples → questions). Lenses to consider (adapted from PM Skills edge cases): input validation, boundaries, error states, permissions, concurrency, recovery. A lens not supported by a source becomes `status: proposed` with a `rationale`, or a question — never a confirmed criterion. Never invent thresholds, messages or limits.
- Tasks: map to criteria/claims; no generic "do frontend"; testing tasks plan work, they are not Test Cases.
- Fields: only proposals with rationale (`state: proposed`) or values confirmed by claims (`state: confirmed`, `claims: [...]`). Never assignee, dates, iteration, completed or remaining work.
- Every effective claim gets one disposition: COVERED (covered_by items/criteria that trace back to it), PARTIALLY_COVERED, NOT_COVERED, QUESTION_REQUIRED, CONFLICTING, OUT_OF_SCOPE or DEFERRED, with rationale. Superseded claims are handled by their decision; active work must not trace to them.
- Items without claims need `technical_rationale` (explicit proposal).

## Readiness and blocking questions
Being confirmed by a source is not the same as being ready to build. Every buildable item (story, enabler, spike, bug, task) declares `readiness` with `status` (`ready`, `partial`, `blocked`, `deferred`, `unassessed`) and a `rationale` that says why it can or cannot be built now.
- Judge each open question: does the missing or conflicting information actually prevent a specific piece of work? Only then is it `blocking: true`. A question about wording, a threshold another item does not need, or an optional detail is non-blocking and must not block unrelated work.
- Work that needs the answer is `blocked` (or `deferred` when it is consciously postponed) and cites the question in `readiness.blocked_by` (`{"ref": "Q2", "rationale": "the gateway integration needs the provider and its contract"}`). Never present it as ready to build, and never encode the dependency in prose alone.
- A bounded spike, a mock contract or an independent part of the work can stay `ready` when its outcome does not need the answer: list the question in `readiness.independent_of` with why. Do not disguise implementation as a spike.
- Every work item a blocking question `affects` is either blocked by it or independent of it, with a reason. A blocking question must block at least one item.
- A story whose tasks are partly blocked is `partial`, not `ready`, and cites the blocking question in its own `blocked_by` (with what part waits for it). Blockers propagate through confirmed `predecessor` relations (an item that waits for blocked work is not ready), not through the hierarchy alone: siblings keep their own readiness.
- Closing a question needs an authoritative decision with provenance; until then the work stays blocked.

## Contract
```json
{"designer": {"agent": "designer-1", "model": "<actual model>", "independence": "separate_agent"},
 "items": [
  {"key": "E1", "type": "epic", "title": "...", "parent": null, "claims": ["C1"],
   "content": {"kind": "epic", "objective": "...", "context": "...", "in_scope": ["..."], "out_scope": ["..."], "outcome": "..."}},
  {"key": "F1", "type": "feature", "parent": "E1", "title": "...", "claims": ["C1"],
   "content": {"kind": "feature", "capability": "...", "value": "...", "rules": ["..."]}},
  {"key": "US1", "type": "story", "parent": "F1", "title": "...", "claims": ["C1", "C2"], "acceptance_style": "gherkin",
   "content": {"kind": "role_goal_benefit", "actor": "<actor from source>", "want": "...", "benefit": "..."},
   "fields": {"story_points": {"state": "proposed", "value": 3, "scale": "fibonacci", "rationale": "..."}},
   "readiness": {"status": "partial", "rationale": "registration is buildable; payment waits for the provider decision"}},
  {"key": "EN1", "type": "enabler", "parent": "F1", "title": "...", "claims": ["C7"],
   "content": {"kind": "enabler", "capability": "...", "outcome": "..."},
   "readiness": {"status": "ready", "rationale": "..."}},
  {"key": "T1", "type": "task", "parent": "US1", "title": "...", "claims": ["C2"],
   "content": {"kind": "task", "summary": "...", "activities": ["..."], "outcome": "...", "verification": "..."},
   "readiness": {"status": "blocked", "rationale": "...", "blocked_by": [{"ref": "Q1", "rationale": "..."}]}}],
 "criteria": [
  {"key": "AC1", "parent": "US1", "condition": "...", "trigger": "...", "expected_outcomes": ["..."], "claims": ["C1"]},
  {"key": "AC2", "parent": "US1", "text": "...", "expected_outcomes": ["..."], "claims": [], "status": "proposed",
   "rationale": "edge case not stated in sources"}],
 "relations": [{"type": "predecessor", "source": "EN1", "target": "US1", "status": "proposed", "reason": "..."}],
 "questions": [{"key": "Q1", "text": "...", "impact": "...", "alternatives": ["..."], "blocking": true, "affects": ["C3", "US1", "T1"]}],
 "dispositions": [{"claim": "C1", "status": "COVERED", "covered_by": ["US1", "AC1"], "rationale": "..."}]}
```
Writing the parts: the runtime adds the bold prefixes, so do not repeat them. In pt-BR `want` follows **gostaria que** and must be a subjunctive clause ("o sistema registrasse a rega", not "registrar a rega"); `benefit` follows **para** (infinitive: "acompanhar a temporada"); job stories: `situation` follows **Quando**, `motivation` follows **quero**, `outcome` follows **para que** (subjunctive). In English `want` follows **I want** ("to …") and `benefit` follows **so that** (a clause). Criteria get visible IDs per story (CA-01, CA-02 … restart in each story), so neither a visible ID nor a design key such as "AC7" may appear in item or criterion text (the runtime rejects both): describe the behavior instead, and relate work to criteria through shared claims.

Content kinds: `epic`, `feature`, `role_goal_benefit` or `job_story` (story), `enabler`, `spike` (question, decision, optional timebox), `task`, `bug` (observed, expected, steps). The runtime renders native HTML (bold **Eu como / gostaria que / para** in pt-BR, **As a / I want / so that** in English) and criterion IDs (CA-01 / AC-01). Inline `**bold**` and `[label](https://…)` are allowed in text.

Write every payload as UTF-8 (for example `open(path, 'w', encoding='utf-8')` or your file-writing tool); avoid shell heredocs for large JSON.
