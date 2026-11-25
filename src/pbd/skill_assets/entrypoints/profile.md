# /pbd-profile

- `pbd profile show [<id>]` lists or prints a builtin process profile.
- `pbd profile execution [economical|balanced|rigorous]` prints an execution profile (concurrency, capability tier per role, delegation, independence). Pass it to a run with `pbd start --execution <name>`; the work order carries it. Tiers map to whatever models the host has; the run records the model that actually ran.
- `pbd profile infer <backlog.json|.csv> [--type-map map.json] [--id team-x]` reports the conventions observed in an existing local backlog (native types, hierarchy pairs, fields in use, acceptance formats) and a **draft** custom profile (`verified: false`). Present it to the owner; it is used only after approval, as `--profile <file>`. Observations describe one file, not a tracker configuration.
