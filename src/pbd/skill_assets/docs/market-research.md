# Market research and design rationale

Documentary comparison consolidated 2026-11-24. This is not an executed benchmark or full source-code audit; commercial capabilities are vendor claims. Missing evidence is not proof of missing functionality. Verify versions, licenses and behavior before adopting code.

| Reference | Observed approach / opportunity for PBD |
|---|---|
| [Microsoft HVE Core](https://github.com/microsoft/hve-core) | prd-builder, functional-planner, backlog-management; planning artifacts, review, multi-tracker operations, duplicate checks, capacity, resume. Primary baseline; use portable canonical JSON and independent atomic review, avoid fixed AC count. Check component-specific CC-BY/CC-BY-SA/MIT terms. |
| [Azure Prototype](https://github.com/Azure/az-prototype) | Python Azure CLI extension, PM agent, backlog generation/publishing, provider separation and cache. Avoid requiring prototype framework/cloud infrastructure. |
| [Azure DevOps Skills](https://github.com/microsoft/azure-devops-skills) | official operation guidance, adapter reference |
| [Azure DevOps MCP](https://github.com/microsoft/azure-devops-mcp) | interactive work item operations; REST remains deterministic transport |
| [BMAD](https://github.com/bmad-code-org/BMAD-METHOD) | analyst/PM/architect/dev/QA workflows, adaptive planning, progressive refinement; avoid forcing full lifecycle |
| [Spec Kit](https://github.com/github/spec-kit) | constitution, specify, clarify, plan, tasks, analyze; cross-artifact analysis and extensions; stable identities beyond text |
| [Task Master AI](https://github.com/eyaltoledano/claude-task-master) | JS/TS CLI/MCP, JSON task state, complexity, expansion, dependencies; preserve business hierarchy and criteria |
| [OpenSpec](https://github.com/Fission-AI/OpenSpec) | proposals, design, tasks, spec deltas and archive; incremental impact and identity |
| [PRD to Jira](https://github.com/punit-labs/prd-to-jira-skill) | agent semantic JSON, Python render CSV/MD; enforce references and links deterministically |
| [PM Skills](https://github.com/product-on-purpose/pm-skills) | product workflows, story quality, edge cases and evaluations |
| [Agile Story Skills](https://github.com/alwyndsouza/agile-story-skills) | INVEST, Gherkin, DoR/DoD and splitting |
| [FrontierSquad](https://microsoft.github.io/frontiersquad-copilot/skills/work-items/) | work items and estimates |
| [Janus](https://janosmart.com/) | vendor BRD-to-backlog beta, visual preview, custom fields and providers; internal implementation not inspected |
| [Copilot4DevOps](https://www.copilot4devops.com/) | vendor requirements analysis, INVEST/MoSCoW, impact, stories/tests; internal implementation unknown |
| [Modern Requirements](https://www.modernrequirements.com/) | baselines, reviews, traceability, reports; offline evidence dashboard reference |
| [Kiro](https://kiro.dev/) | EARS, structured specs and properties |
| [QVscribe](https://qracorp.com/) | deterministic requirement quality checks |
| [Atlassian Rovo](https://www.atlassian.com/software/rovo) | Jira refinement and decomposition |
| [DevOps Assist AI](https://marketplace.visualstudio.com/items?itemName=DevOpsAssist.devops-assist-ai) | Azure AI work item planning |
| [StoryPilot](https://marketplace.visualstudio.com/items?itemName=devirsa-labs.storypilot-azure-devops) | stories and acceptance refinement |
| [AI Work Item Assistant](https://marketplace.visualstudio.com/items?itemName=ms-adowia-external-dev.workitem-assistant-extension-external) | work item/child generation |
| [SprintBridge](https://marketplace.visualstudio.com/items?itemName=OrCohen.sprintbridge) | VS Code backlog and sprint operations |

## Comparative dimensions
PRD-to-backlog, hierarchy, tasks/dependencies, semantic audit, capacity, Azure publication, incremental changes, canonical state, visual reporting. HVE is closest open reference; Janus closest commercial generation reference; Modern Requirements reporting reference. Spec Kit and BMAD are broader development methodologies; Task Master focuses on technical tasks; OpenSpec on change; PRD to Jira on conversion. No superiority claim until controlled experiments.

## Engineering responses
Missing table obligations → source inventory and independent recall; fabricated rules → provenance/questions; generic stories → INVEST; overproduction → value slices; duplicate tickets → stable ID/reconciliation; invented estimates → proposals; missing capacity → no committed sprint plan; human edits → revision checks; interrupted writes → journal; false coverage → independent gold and semantic evidence; unsafe publication → exact plan approval. See [architecture](architecture.md), [benchmarks](../benchmarks/README.md).

Additional references: [Scrum Guide](https://scrumguides.org/), [Agent Skills](https://agentskills.io/), [Anthropic Skill Creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator).
