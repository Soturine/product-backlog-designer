# Work item writing and profiles

## Default rich-text conventions
- Epic: **Objective**, **Context**, **In scope**, **Out of scope**, **Expected outcome**; only supported scope.
- Feature: capability, value, expected outcome, related rules; concise.
- Functional Story: **Eu como** [actor], **gostaria que** [capability], **para** [benefit]. English: **As a** … **I want** … **so that** …. Support Job Stories, Enablers and other approved formats; no invented actor.
- Acceptance criteria: separate native field, one observable obligation per criterion where practical; positive/negative/edge cases when supported. Bullet lists or Gherkin, no fixed count.
- Task: action-oriented title, concise description, activities, expected output, validation and dependencies where necessary. Scale detail to complexity. Distinguish Development, Design, Testing, Requirements, Deployment, Documentation or destination-supported activities. Test Tasks are not Test Cases.
- Preserve Unicode, paragraphs, bold, lists, links and tables where supported; render native HTML, not raw Markdown in HTML fields.

Example: `<p><strong>Eu como</strong> operador, <strong>gostaria que</strong> o sistema registrasse pedidos, <strong>para</strong> organizar solicitações.</p>`. Criteria: `<ul><li>Um pedido válido fica disponível para consulta.</li></ul>`.

## Field policy
| Category | Fields and handling |
|---|---|
| Identity | Title/type generated; ID/revision server-managed |
| Content | Description and native Acceptance Criteria; preserve original raw values |
| Planning | Priority, Risk, Effort, Story Points, Size: proposals with rationale and scale |
| Value | Business Value, Time Criticality, Value Area: evidence or explicit unknown |
| Effort | Original Estimate, Remaining Work only supported/approved; Completed Work and Time Logged never fabricated |
| Classification | Activity, Tags, Area Path, Iteration Path from discovered rules |
| Schedule | Start Date, Target Date only confirmed; suggestions remain local |
| Workflow | State initial allowed; Reason server/policy; Assigned To authorized identities only |
| Relations | Parent/Child, Related, Predecessor/Successor; no invented development links |
| Quality | DoR/DoD according to team policy; extension-backed data requires separate verified contract |
| Evidence | Hyperlinks, attachments, branch/commit/PR/build references only when real and authorized |
| Custom | Discover type, requiredness, writability, allowed values, defaults, rules; preserve unknown values in snapshot |

Unset, unknown, inferred, proposed, confirmed, server-managed and not-applicable are distinct. Never fill blanks with fake data. Field-level provenance and review status required for proposed values.

## Profiles
Generic; Azure Agile (Epic/Feature/User Story/Task), Scrum (PBI), CMMI (Requirement), Basic (Epic/Issue/Task), custom, GitHub and Jira (future). Discover actual types and hierarchy; profile is a default, not truth. Profile includes language, title patterns, HTML style, field mappings, allowed states/activities, estimation scale, priority, hierarchy, DoR/DoD and output formats. A profile learned from existing backlog requires approval and cannot override requirements or reproduce errors.

See [synthetic example](../examples/order-management.md) and [Azure adapter](azure.md).
