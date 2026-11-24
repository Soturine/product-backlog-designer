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
