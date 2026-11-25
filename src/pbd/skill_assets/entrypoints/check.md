# /pbd-check

Structural health of a backlog file without sources: `pbd check <backlog.json|.csv> [--type-map map.json]`.

- Canonical backlogs are validated against the schema and invariants (hierarchy, references, cycles, supersession).
- Imported files report stories without criteria, children of tasks and containers under work items; equal titles are only duplicate **candidates**.
- Empty optional fields and open parents are reported as information, never as defects.
- Without normative sources nothing is said about coverage, invention or scope (`scope: structural_only`). For that, run an audit with sources ([audit](audit.md)). Gates of a finished run are in its `output/gates.json`.
