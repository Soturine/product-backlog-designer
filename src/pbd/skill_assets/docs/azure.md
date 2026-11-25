# Azure DevOps adapter (planned)

Primary transport REST API; Azure CLI/Azure Identity for credentials, MCP as optional interactive adapter. Never embed tokens. Discover organization/project GUID, team, process, work item types, fields, required rules, allowed values, relation types, areas, iterations, dates, team capacity and backlog levels. See [official REST API](https://learn.microsoft.com/en-us/rest/api/azure/devops/) and [MCP](https://github.com/microsoft/azure-devops-mcp).

## Export
Use WIQL with explicit project scope and JSON request body; fetch detail batches of at most 200 with relations, reconcile all IDs and project identity. Preserve raw UTF-8 HTTP response and unknown/custom fields; do not route through locale-dependent shell decoding. Handle query limits, truncation and continuation; record snapshot time, revisions, hashes, missing IDs and permission errors. Export team iteration/configuration, comments/revisions/attachments only if separately requested/authorized. Test Plans/Suites/Runs are separate surfaces; FTD owns Test Case creation. Distinguish inaccessible from empty.

## Field mapping
Discover actual reference names and types; map System.Title, System.Description (safe HTML), Microsoft.VSTS.Common.AcceptanceCriteria when available, priority/risk/effort/points/value/time criticality/activity, estimates, tags, classifications, dates, identities and custom fields. Read-only/derived fields not written. Preserve HTML formatting and UTF-8; DoD/time tracking extensions need verified contracts. Never bypass rules.

## Prepare/apply/verify
1. Read snapshot and discover schema; compute CREATE/UPDATE/UNCHANGED/CONFLICT/DEFERRED operations (automatic DELETE forbidden).
2. Match stable PBD identity to tracker ID, never title alone; legacy adoption requires explicit reconciliation. Topological order parents before children; typed links separately when needed.
3. Produce exact field/link diff, preconditions and target identity. Use validateOnly where supported; no mutation during prepare.
4. User approves exact plan hash, target and scope. Reject stale plans, invalid gates, ambiguous matches or changed revision. Apply JSON Patch with revision test for updates, least privilege and no bypass.
5. Journal request intent and result; on ambiguous create timeout re-query identity before retry. Respect throttling, bounded retries; stop on unexpected state. Resume only after reconciliation. No claim of cross-item transaction or automatic rollback.
6. Re-export and compare semantic field values, normalized HTML, hierarchy, relations and expected revisions; record partial failures and receipt. Reapply identical desired state should produce zero creates/updates.
7. Never assign people, change state, create iteration/area, or publish private attachments without explicit authorized plan.

Azure CLI integration must support PowerShell 5.1, Windows and Unix UTF-8. Sandbox live qualification separate from mock tests. GitHub/Jira future adapters must disclose hierarchy limitations.

See [security](security.md) and [work items](work-items.md).

## CLI-friendly import bundle
The default local Azure package contains azure-import.json (PBD contract with local IDs, typed relations, field values, provenance, explicit unknowns), manifest, and an optional native portal CSV subset. A JSON file alone is not a native bulk import command. Use a deterministic PBD publisher, with Azure CLI authentication and REST JSON Patch as primary path; optional CLI wrapper for supported operations. Planned invocation: `pbd azure publish --package azure/azure-import.json` prepares only; after approval the same workflow applies the exact plan. Provide Windows PowerShell 5.1 and Unix launch instructions; no embedded secrets, shell interpolation or generated ad hoc scripts that bypass gates. A wrapper may use `az boards work-item create` and `az boards work-item relation add` where appropriate, checking every return code, but REST is preferred for revision tests, native HTML and precise payload. Verify all remote operations; a create with failed parent link is PARTIAL, not success.

Optional manual fallback: Azure Boards CSV import supports hierarchy using indented Title columns, but not arbitrary relation types; discover field support and report fidelity limits. Do not promise CSV preserves the entire canonical backlog or all custom fields. [CSV docs](https://learn.microsoft.com/en-us/azure/devops/boards/queries/import-work-items-from-csv?view=azure-devops), [CLI](https://learn.microsoft.com/en-us/cli/azure/boards/work-item?view=azure-cli-latest), [create API](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create?view=azure-devops-rest-7.1). Validate only where supported; no live write in design demo.

## Offline implementation and calibration boundary
Development, tests and benchmarks use local snapshots and mock transports exclusively. Do not authenticate or contact a live Azure organization, including read requests or validateOnly. A future separately authorized disposable environment may be used for live qualification; otherwise mark live checks NOT_RUN. A prepared package is never approval to write. See [master directive](PBD_AGENT_LED_MASTER_DIRECTIVE.md).
