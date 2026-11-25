# /pbd-audit

Design-stage agent procedure; the runtime CLI is not implemented. Follow [SKILL](../SKILL.md), [commands](../docs/commands.md) and [quality gates](../docs/quality-gates.md).

Inputs: functional authority, existing backlog snapshot and optional technical sources. Freeze original snapshot; audit every source claim, epic, feature, story, criterion and task individually. Record expected vs actual, evidence, severity, impact, disposition and suggested change. Distinguish missing access from missing data. Read-only; do not silently correct.

Follow [methodology](../docs/methodology.md) and [story/criteria guidance](../docs/story-engineering.md). Use only authorized inputs and disclose unexecuted checks.
