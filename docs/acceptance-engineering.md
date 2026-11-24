# Acceptance criteria engineering

Status: normative design guidance; automated implementation pending.

## Contract
A criterion states an externally observable behavior or evidence-based quality constraint for acceptance of a work item. It is not a development activity, a test execution result, or a team-wide Definition of Done. Use a stable criterion ID, parent Story ID, claim IDs, source locators, condition/trigger/outcome, style, status, and rationale. Keep native Azure acceptance field separate from description. Do not invent threshold, error text, data rule or integration behavior. Unknown outcome becomes a question, not a passing criterion.

## Generation workflow
- Review each atomic obligation, actor, precondition, event, business rule, state, data and expected effect.
- Use Example Mapping to separate story, rules, concrete examples and unresolved questions. For each rule identify representative outcomes and exceptions when supported.
- Choose simple bullet criteria for straightforward behavior, Given/When/Then for context-sensitive behavior, decision tables for meaningful combinations, state transitions for lifecycle rules, and EARS for structured requirements. These are not mandatory interchangeable formats.
- Assess relevant partitions: valid/invalid inputs, required/optional values, min/max/equality, permission, state, integration failure/retry, persistence, consistency, concurrency, recovery, accessibility, security and performance. Consider applicability, evidence and risk; mark unsupported cases as proposed or questions. Do not generate all combinations mechanically.
- Check independent reviewer coverage against authority, not just generated criteria. Trace missing, partial, conflicting, unsupported and covered behavior. Retain criterion IDs across wording changes.
- Write clear expected outcome, including forbidden side effects where warranted; avoid vague terms, subjective adjectives, ambiguous pronouns, undefined units, hidden conjunctions, unbounded 'etc.' or unexplained thresholds. Flag ambiguous language for review, not automatic rejection.

## Styles
Bullet: “When a member attempts to reserve an unavailable title, the system rejects the request without creating a reservation.”
Gherkin: Given a title has no available copies / When a member requests a reservation / Then no reservation is created. Prefer domain language, not button clicks or implementation details unless UI behavior itself is required. Scenario Outline with examples for meaningful data partitions; one behavior per scenario where practical.
EARS patterns: ubiquitous (always), event-driven (when event), state-driven (while condition), unwanted behavior (if condition then response), optional-feature (where feature is present), combinations where necessary. EARS constrains requirement language; it is not a substitute for examples, tests or business decisions.

## Review rubric
For every criterion record: source support, testability, specificity, scope, consistency, coverage, nonredundancy, outcome observability, ambiguity, and applicable error/edge behavior. Distinguish confirmed, inferred proposal, blocked, out-of-scope. A criterion referencing another story must have a resolvable link. An unverified assumption cannot be silently accepted. A passing schema or valid Gherkin is insufficient for semantic quality.

## Example (fictional)
Source R1: available title can be reserved; R2: unavailable title cannot be reserved; R3: success appears in the member's reservations.
- AC1/R1: request for available title creates a reservation.
- AC2/R2: unavailable title request creates no reservation.
- AC3/R3: created reservation appears in the member list.
Question: how long is a reservation held? No duration specified; do not invent it.
Poor criterion: “Reservation works quickly with no bugs.” Missing measurable conditions, expected behavior and authority.
Task: implement availability check. Test Case: concrete inputs, preconditions, steps, expected results. DoD: team-wide quality policy. Different artifacts.

See [story engineering](story-engineering.md), [gates](quality-gates.md), [sources](research-references.md).
