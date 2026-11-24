# ADR-0001 — M0 runtime foundation

Status: accepted for M0 (2026-11-24). Scope: runtime contracts only; no semantic engine, renderer or tracker transport.

## Context
The [master directive](../PBD_AGENT_LED_MASTER_DIRECTIVE.md) requires strict versioned canonical schemas, stable identity, path/archive safety, atomic state, checkpoint invalidation, privacy tests, CLI help and a zero-network default before generation work starts. The repository owner has not chosen a license, so third-party code cannot be incorporated.

## Decisions
1. **Original implementation, concepts only.** No upstream file is copied or vendored. FTD (scoped sources, atomic baseline, emitted-field hash) and Assertiva (gate status semantics: executed vs absent evidence) informed design at the concept level only. See [upstream pins](../upstream-pins.md).
2. **Dependencies.** Runtime: Python ≥ 3.11 standard library plus `jsonschema` (MIT; transitive `referencing`, `rpds-py`, `attrs`, `jsonschema-specifications` — MIT/Apache-2.0). Dev-only: pytest, hypothesis, ruff, mypy, coverage. No HTTP client, cloud SDK, LLM SDK, database or Docker. Pydantic from the proposed stack is deferred: JSON Schema is the contract, and a second model layer would duplicate it.
3. **Schemas** live in `src/pbd/schemas/v1/` (bundled into the wheel so the installed skill works offline), Draft 2020-12, `additionalProperties: false`, `urn:pbd:schema:v1:*` IDs, remote `$ref` retrieval refused. `schema_version` is semver `1.x.y`; incompatible changes require `v2/` plus migration notes.
4. **Identity.** `PBD-<KIND>-<12 Crockford base32>`; minted randomly or derived from an explicit provenance anchor (source + locator). Anchors keyed by title/name/position/index/order are rejected. Tracker IDs live only in `external_refs` (`system`, `namespace`, `native_id`) and may never start with `PBD-`.
5. **Field provenance.** `unset`, `unknown`, `inferred`, `proposed`, `confirmed`, `server_managed`, `not_applicable`, `unavailable` are distinct; value-less states cannot carry a value, proposals need rationale, confirmations need evidence. Zero is a value, not an absence.
6. **Evidence is typed** (`source_locator`, `decision`, `review`, `deterministic_check`, `tracker_snapshot`, `code_observation`, `test_plan`, `executed_test`, `user_statement`); a test plan never substitutes for an executed test.
7. **Gates.** G01–G13 keep their IDs and names; G14–G18 added. PASS requires evidence of the gate's kind; coverage gates (G01, G02, G13) need an independent, complete, non-empty denominator. Tests assert the registry matches [quality gates](../quality-gates.md).
8. **State.** Private `.pbd/runs/<run>/manifest.json` (atomic replace) plus a hash-chained append-only `journal.jsonl`. Stage completion with a changed output, or a changed/added source, invalidates all transitive dependents with a recorded reason. Five status dimensions (run, source coverage, semantic review, publication readiness, remote state) are independent.
9. **Offline boundary.** Every CLI command runs inside an in-process socket/DNS guard; tests run under the same guard with loopback only. Remote writes go through a single default-deny `authorize_apply`; live transport is hard-disabled in this build. DELETE is not representable in a publication plan.
10. **Layout.** `src/pbd/{core,persistence,sources,security,validation,integrations,schemas}` exist because they contain tested code; the other proposed packages from [architecture](../architecture.md) are created only when implemented.

## Consequences
The runtime can validate, inventory and checkpoint, but performs no semantic work and renders nothing yet (M1). Symlink tests need OS symlink privileges; on Windows without them they skip, and junction tests cover link escape instead.
