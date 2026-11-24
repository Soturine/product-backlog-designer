# Changelog

## Unreleased — M0 runtime foundation
- Add `pbd` Python package (3.11+, sole runtime dependency `jsonschema`) and offline CLI: `doctor`, `schema`, `validate`, `inventory`, `id`, `run`, `privacy-scan`.
- Add strict versioned v1 JSON Schemas: backlog (sources, claims, items, criteria, relations, questions, decisions, findings, field provenance, temporal supersession, typed evidence), run manifest, gate report (G01–G18), publication plan (no DELETE) and receipt (mock never live-verified).
- Add opaque stable identity, canonical JSON digests, referential invariants (duplicates, dangling refs, parents, cycles, stale locators, namespace mixing), gate evidence rules, atomic state with hash-chained journal and checkpoint invalidation.
- Add source allowlist with traversal/symlink/junction rejection and in-place archive inspection limits; in-process zero-network guard; privacy scanner; default-deny remote-write authorization.
- Add unit, property, contract, security and docs-link tests with synthetic fixtures; ADR-0001, threat model, install guide, upstream pins and M0 evidence. No generation, rendering, tracker access or release.

## Unreleased — design baseline
- Define single agent-first skill, architecture, quality gates and source-first methodology.
- Specify native rich text, field provenance, profiles and Azure export/publication contracts.
- Document market references, benchmarks, synthetic fixture and implementation roadmap.
- No runtime, remote adapter, benchmark results or release claimed.

- Expand story and acceptance engineering, task planning, research bibliography and evaluation scenarios; specify mode-specific agent procedures.

- Expand bilingual README, single-entrypoint interaction contract, output/report design, Azure CLI bundle, targeted upstream implementation and license audit, reuse decisions and synthetic dashboard example. No upstream code vendored or runtime qualified.

- Specify source-only default, agent-led execution boundaries, evidence/temporal health, native table acceptance, offline calibration and implementation directive; extend quality gates without renumbering. No runtime or live integration executed.

- Require per-checkpoint commits, pushes, remote verification and authorized Git identity; prohibit AI authorship trailers and unnecessary CI, preserve required attribution and branch protections.
