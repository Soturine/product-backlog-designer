# /pbd-adr

Incremental evolution of an existing canonical backlog after source changes or decisions (ADRs). Never regenerate: update the existing backlog so identities, human edits and history survive.

1. Run [/pbd-diff](diff.md) and read what changed.
2. Write an evolution proposal: the refinement operations ([/pbd-refine](refine.md)) plus
   - `add_decision` (`text`, `status` approved|proposed, `evidence` [source locator or recorded user statement], optional `supersedes_claims` — only an approved decision supersedes);
   - `supersede_item` (`target`, `superseded_by` item or decision IDs, or `change:<key>` for something created earlier in the same proposal);
   - `retrace` (`target` item or criterion, new `claim_refs`): remove a superseded claim from work that still traces it;
   - `answer_question` (`target` question, `decision` an approved decision ID or `change:<key>` of an `add_decision` in the same proposal): closes an open question with its authoritative decision;
   - `set_readiness` (`target` item, `readiness` {status, rationale, blocked_by?, independent_of?}): recompute the readiness of work the answered question blocked — the runtime rejects any blocker that still cites an answered question, so both changes go in the same proposal.
   - `split_item` (`target`, `into` [≥2 parts]) and `merge_items` (`targets`, `title`): new items carry `lineage.split_from`/`merged_from`; the originals stay visible as superseded.
3. `pbd evolve plan --backlog backlog.json --file proposal.json [--diff evo/source-diff.json] --out evo/` validates everything against the schema and invariants (a superseded claim still traced by active work is refused), writes `evolution-plan.json`, `evolution-summary.json` (create/update/unchanged/conflict per item, deletions 0), `evolution-diff.md` and `evolution-report.html`.
4. After the owner's decision: `pbd evolve apply --backlog backlog.json --plan evo/evolution-plan.json --approve <keys|all> --plan-digest <digest> --out evo/`. `all` never includes changes that overwrite human edits; those need their own keys (`override_human_edit` in the proposal).
5. `pbd evolve stale --backlog evo/backlog.evolved.json --dir <artifacts>` lists plans, packages, refinement and publication plans bound to the old digest: produce them again; old approvals never carry over.

Rules enforced by the runtime: nothing is deleted; a title change keeps the ID and an `add_item` with the same type, parent and title is refused as a re-creation; a replayed plan on a newer version is a conflict.
