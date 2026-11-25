# Story engineering playbook

Status: normative design guidance; automated implementation pending.

## Choosing the right artifact
An Epic states a meaningful outcome and scope boundaries; a Feature groups a capability; a Story describes a valuable increment for an actor or stakeholder; a Task describes work to realize it. A bug describes observed versus expected behavior and evidence; an enabler expresses a justified technical capability; a spike resolves a specific uncertainty with a timebox and decision output. Never disguise a task as a user story. A requirement can map to multiple stories or one story may satisfy multiple atomic obligations. Scrum does not prescribe user-story syntax, story points or the Epic/Feature hierarchy.

## Story authoring workflow
1. Read authority and extract actor, goal, value, triggers, state, constraints and exclusions. Mark unsupported elements unknown.
2. Choose the smallest useful vertical slice, preserving the complete user outcome.
3. Write action-oriented title and a concise story. Default pt-BR: **Eu como** [actor], **gostaria que** [capability], **para** [benefit]. English: **As a** … **I want** … **so that** … . Job Story: situation, motivation, outcome. Enablers may use capability/outcome without an invented persona.
4. Apply 3Cs: the card is a conversation starter; unresolved issues become questions; confirmation is observable acceptance, not proof of implementation.
5. Identify rule and examples using [acceptance engineering](acceptance-engineering.md). Record evidence and links, then decompose work.
6. Review INVEST and quality checks; split or revise with rationale. Retain alternate valid shapes. Do not force every story into the same length or number of criteria.

## INVEST review rubric
| Dimension | Evidence to inspect | Corrective option |
|---|---|---|
| Independent | overlapping behavior, real sequencing constraints | remove accidental coupling, retain necessary dependency edge |
| Negotiable | business outcome versus premature implementation | move unmandated design into proposal or technical task |
| Valuable | actor and outcome supported by source | clarify benefit, recategorize enabler/task |
| Estimable | scope, uncertainty, external contracts | ask question or timebox discovery |
| Small | deliverability relative to team and planning horizon | vertical split, not arbitrary point cap |
| Testable | observable outcome and determinate criteria | specify conditions, boundaries and outcome |

Record each as supported, concern, unknown or not applicable, with evidence. Missing team sizing information is not proof a story is too large. Do not compute a fake pass score.

## QUS-inspired quality review
Lucassen et al. describe syntax, meaning and practical interpretability and evaluate AQUSA. Use the research as inspiration, not an assertion of exact conformance or a reproduction of their tool. Check form, atomicity, unnecessary content, problem vs solution, ambiguity, actor/value clarity, consistent domain terms, meaningful dependencies, semantic duplicates, contradictions and completeness of the set. Rules may flag conjunctions, vague adjectives, missing slots, inconsistent terminology or repeated phrases; these are candidates, not confirmed defects. A conjunctive outcome may be indivisible. A valid nonstandard Story need not be rewritten. Semantic review decides with source evidence. Track false positives and negatives by language and story format; support pt-BR and English.

## Decomposition
Map the journey backbone, tasks from the user's perspective, and a minimal usable release slice. Split by workflow paths, business rule variation, data variation, operations, interfaces or alternate outcomes only if each slice remains coherent. Consider happy path plus supported exceptions, not UI/database/API layers as separate value stories. Use a spike for unknown technical contracts. Avoid postponing necessary security, integrity or accessibility into a later slice just to reduce size. Preserve all source claims through split/merge; maintain lineage.

Example: a fictional library can let a member reserve an available title and decline an unavailable title. Two UI/backend layer stories would not provide independently demonstrable value; a reservation slice with both outcomes may be appropriate, or separate slices if policy allows and value remains intact.

## Refinement and readiness
Refine progressively; detail imminent work and preserve future uncertainty. Readiness is a team agreement, not a universal Scrum requirement. Acceptance is story-specific; DoD concerns increment quality; neither replaces executable Test Cases. Priorities, points, dates and assignments must follow [planning](planning-engineering.md). See [sources](research-references.md) and [work-item format](work-items.md).
