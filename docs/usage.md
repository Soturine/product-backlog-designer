# One-skill interaction contract

The user-facing interface is one skill, not a chain of mandatory slash commands. Natural language is the default, and /pbd is the proposed umbrella entrypoint. Commands remain optional; the agent routes internal stages automatically. Do not claim these commands are installed before qualification.

## Intent routing
| User intent | Internal workflow |
|---|---|
| "Generate a backlog from this PRD" | inventory → claims → generate hierarchy, criteria, tasks → independent audit → gates → render |
| "Check my existing backlog against these documents" | freeze snapshot → source-first audit → item/criterion review → report; no remote writes |
| "Compare two backlogs" | isolate generation if requested → semantic alignment → differences and evidence |
| "Only write tasks for these stories" | selected-level generation with parent and source context |
| "Update after this ADR" | impact and reconcile, no full regeneration |
| "Prepare this for Azure" | local package; remote discovery only with authorized target |
| "Publish to Azure" | discover, snapshot, prepare exact plan; pause for approval; then apply and verify |
| "Show me the report" | render canonical state without changing semantic decisions |

## Minimal input and defaults
Generation from zero is the default. Only explicitly selected sufficiently informative sources and goal are necessary; no existing backlog, tracker, credentials, code or TDD is mandatory. Infer language from the request unless specified; default output is report.html + backlog.json and supporting evidence JSON. No remote reads unless target and authorization are clear; no remote writes without separate exact-plan approval. If Azure is selected, automatically prepare a local import package when applicable. If destination is unspecified, remain tracker-neutral. If sources or authority are ambiguous, ask only blocking questions or mark the affected scope as blocked; continue unaffected work. Do not ask the user to choose agents, stages, gate numbers or output filenames.

One semantic reader per declared source (one directory counts as one), with bounded subchunks when needed. If the host cannot spawn readers, perform sequential source-scoped reviews and disclose reduced independence. Never use a generated program or lexical shortcut to replace actual semantic review. Read only selected sources.

## UX acceptance
- First useful output from one natural-language request; no forced configuration wizard.
- Internal steps show progress with evidence, but do not require manual command chaining.
- Restart resumes valid checkpoints; changed sources invalidate dependent work.
- A default report links all evidence and outputs; the user does not need to open a dozen files.
- Optional expert controls use existing [commands](commands.md); all modes respect the same guards.
- No model API keys or paid service needed beyond the chosen agent host for local operation; Azure CLI/auth only required for remote integration.
- Explicit review boundary separates generation completion, quality status and publication. Report failures/unknowns rather than claiming success.

Development and benchmarking remain offline, using local snapshots or mocks only. A local Azure package does not imply any contact with Azure.
