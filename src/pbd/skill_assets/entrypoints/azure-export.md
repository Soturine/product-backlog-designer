# /pbd-azure-export

**Mock only.** This build has no live transport: nothing authenticates to, reads from or writes to a real Azure DevOps organization, not even read-only or validateOnly. Inputs are local files the owner exported and authorized; the target is an in-memory mock saved to a local JSON file. A mock result never proves a live target.

`pbd azure snapshot --file <local export.json> [--org O --project P] --out <dir>` normalizes a local snapshot (REST-shaped work items with `id`, `rev`, `fields`, `relations`, one or more pages) and writes `azure-snapshot.normalized.json` plus `azure-discovered-profile.json` (process guess, native types, fields with required/allowed values/read-only when the export includes metadata). Duplicate items with different revisions are refused; a trailing `continuationToken` is reported as truncation; missing fields or relations are `unavailable`, never defaulted. PBD itself never exports from a live project in this build.
