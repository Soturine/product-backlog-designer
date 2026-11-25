# /pbd-refine

Design-stage agent procedure; the runtime CLI is not implemented. Follow [SKILL](../SKILL.md), [commands](../docs/commands.md) and [quality gates](../docs/quality-gates.md).

Inputs: selected work items, current snapshot, authority and desired change. Identify impact and dependent items; propose minimal before/after changes, preserve IDs and untouched fields, record split/merge lineage and questions. No remote writes.

Follow [methodology](../docs/methodology.md) and [story/criteria guidance](../docs/story-engineering.md). Use only authorized inputs and disclose unexecuted checks.
