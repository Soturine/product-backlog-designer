# /pbd-azure-publish

Design-stage agent procedure; the runtime CLI is not implemented. Follow [SKILL](../SKILL.md), [commands](../docs/commands.md) and [quality gates](../docs/quality-gates.md).

Prepare: freeze snapshot and compute exact operations, plan hash, revision preconditions and preview. Apply: require explicit approval of exact hash and target; use revision checks, journal, reconcile ambiguous creates, halt conflicts. No automatic deletion. Report actual operations and verification; never claim success without read-back.

Follow [Azure safety protocol](../docs/azure.md). Use only authorized inputs and disclose unexecuted checks.
