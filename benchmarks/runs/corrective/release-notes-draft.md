# Release notes — DRAFT (not a release)

Draft for the owner's release review. No version was changed, no tag or release created, nothing published to PyPI.

## Highlights since the final integrated qualification
- **Is it ready to build?** Backlog schema 1.2.0 adds agent-judged readiness with typed links to the blocking question or dependency; the runtime rejects contradictions, the independent reviewer agrees or disputes, G08 shows it, and planning never schedules blocked work. Older backlogs stay valid and show as *not assessed*.
- **Report as a review tool:** development readiness and what each blocking question holds up; every quality gate explained (purpose, why it matters, evidence type, status meaning, affected work, recorded next step) with a glossary; sortable work-item table; presentation-only Generic / Azure DevOps / Jira appearance with original pictograms; accessibility fixes from an axe-core scan.
- **Team planning:** two-sprint, two-developer plans with one accountable owner per story, task assignees, per-person capacity in its own unit, preparation and carryover, unknown estimates never treated as zero; local drafts only.
- **Evolution and publication:** close a question with an approved decision and recompute readiness; build the local Azure package from any canonical backlog; the approval-gated in-memory mock round trip. No live tracker access exists.
- **Native-first:** PDFs without a text layer are read natively with a recorded transcription.

## Known limitations (see the ledger)
- QL-020 generator variance in classifying blocking questions (surfaced by the reviewer, not fixed by rules).
- QL-017 DOCX/XLSX originals cannot be opened natively by the Claude Code host (declared fallback).
- QL-011 manual accessibility review not performed; QL-015 automatic discovery on Codex not proven; QL-008 Linux not exercised; QL-021 FTD outputs carry no PBD IDs.
- Live Azure DevOps/Jira: not supported; mock results never prove a live target.
- Report size at the 1,060-item reference fixture is 6.57 MB of a 7 MB budget.
