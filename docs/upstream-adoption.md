# Upstream research and adoption decisions (M0 corrective + M1)

Clones of external projects live outside this repository in a sibling `pbd-upstreams/` folder (shallow, hooks disabled, nothing executed). The owner's projects (FTD, Assertiva, Derivanta, Derivanta Engine, QE Engineering) were used from their existing local checkouts, unmodified. Evidence types: **S** = static code reading, **X** = executed locally, **T** = adopted and covered by PBD tests.

## Pinned versions
| Project | Commit | License | Source |
|---|---|---|---|
| Functional Test Designer | 314e8d6dd9a81ee533fe46f87da293e0b981b7ab | MIT | local checkout |
| Assertiva | d4d8d49201ce0461cbc180798344f2518c2901f0 (CLI 1.0.0) | Apache-2.0 | local checkout |
| Derivanta | 218761dbd7ce78809ace0ae2c03ee23adf9b406b | Apache-2.0 | local checkout |
| Derivanta Engine | acd6ca3263c4b668357ad9fdd830cc02f5e39d51 | Apache-2.0 | local checkout |
| QE Engineering Skill | 73a6d7b5eb0db3df8a7b4cb6fb0bd4ccc73cb731 | not declared in pyproject | local checkout |
| microsoft/hve-core | 732da19c98b3ac27292c001780036807a2d8a49d | MIT | clone |
| Azure/az-prototype | afb8821da0bb88cfa433dbe3e475b8e4910403ea | MIT | clone |
| github/spec-kit | 7def2cdeaa74024147ccc80763fe77c30ce44ef4 | MIT | clone |
| bmad-code-org/BMAD-METHOD | e435a22574fe55722841086e5566420178b98df3 | MIT | clone |
| Fission-AI/OpenSpec | b30672cce4937f0a598dd793ae1a5eda23606e25 | MIT | clone |
| product-on-purpose/pm-skills | 3456e5e309f38ac2a66943f20d4aaf8031268dfb | Apache-2.0 | clone |
| punit-labs/prd-to-jira-skill | 81bdea0a2c82c8588dbf12404ef2ff2c42f519b9 | MIT | clone |
| microsoft/azure-devops-mcp | 2db70041a9bce29d228b4d8cbaea214541fc3ca9 | MIT | clone |
| microsoft/azure-devops-skills | b418a6c8fa9fd622274882a1378e664df746f356 | MIT | clone |
| alwyndsouza/agile-story-skills | 248cf3fd0764325ab5cbbf87dd9389fba99be20e | **none found** | clone |
| eyaltoledano/claude-task-master | c0c98d367c55296bfe69e65680625b6db437af02 | MIT + Commons Clause | clone |

## Decisions by subsystem
| Subsystem | Upstream component | Decision | Evidence | What PBD does / why |
|---|---|---|---|---|
| Report design system | Assertiva `report_html.py` CSS tokens | **DIRECT_REUSE** (token block verbatim) | S, T | Mature light/dark palette and tone system; attribution in [third_party](../third_party/README.md). Components/markup original because Assertiva's model is test-assurance specific. |
| Report patterns | Assertiva bilingual pairs, `<details>` expansion, next-step rail | ADAPT | S, T | Bilingual UI labels, server-side complete content, details/summary tree. |
| Link types / patch | azure-devops-mcp `work-items.ts` link map, `test /rev`, `multilineFieldsFormat` | **PORT** (link map) + CONCEPT (patch) | S, T | Local Azure package uses exact reference names, HTML multiline format and JSON Patch; `test /rev` reserved for M3 updates. |
| Agent-led orchestration | FTD `pipeline.py`, `reading.py`, stage contracts, work order | ADAPT (concept, original code) | S, T | Work order per stage, one reader per declared selector, all-or-nothing submissions, digest binding, forbidden reader decisions, templated-output rejection. PBD adds quote verification against cited lines (FTD only checks line ranges). |
| Gate semantics | FTD validation builder; Assertiva gate evaluator | REIMPLEMENT | S, X, T | FTD returns PASS when the pipeline "should" have enforced; PBD binds every PASS to re-hashed artifacts, run and stage (`verify.py`). Assertiva's executed-vs-absent distinction kept. |
| Story/level quality | HVE Core `story-quality.md`, `ado.md` | ADAPT (procedure text, original wording) | S | Level-specific quality, sizing signals as reviewer candidates. **Rejected**: fixed 5–10 criteria per story; criteria inside description. |
| Edge-case lenses | PM Skills `deliver-edge-cases` | ADAPT | S | Lenses in designer procedure with a proposal-only rule when not sourced. |
| Consistency analysis | Spec Kit `analyze.md` | ADAPT | S | Six detection passes + severity rubric in reviewer procedure. **Rejected**: keyword-based task coverage mapping. |
| Validation shape | OpenSpec `validator.ts` | CONCEPT_ONLY | S | ERROR/WARNING/INFO split mirrors PBD hard invariants vs candidate signals; delta validation revisited in M5. |
| Manifest checks | BMAD `validate_manifests.py` | CONCEPT_ONLY (M5/M6) | S | Skill manifest validation idea for multi-host packaging later. |
| CSV rendering | prd-to-jira `render_outputs.py` | REJECT (code) | S | Uses platform-default encoding and no formula guard; PBD writes UTF-8 BOM CSV with formula-injection guard. |
| Dependency graph | Task Master `dependency-manager.js` | CONCEPT_ONLY (license) | S | Commons Clause; PBD uses `graphlib` over the whole graph with cycle path in the error. |
| Backlog push/state | az-prototype `backlog_push.py`, `backlog_state.py` | REJECT (code), CONCEPT for M3 | S | Criteria mixed into description, unchecked link exit codes, position-indexed state. PBD keeps native acceptance field, stable IDs, journal. |
| Backlog summary skill | azure-devops-skills | REJECT for export | S | Filters to current-user active items; PBD requires complete explicit scope. |
| Story splitting | agile-story-skills | REJECT (no license) | S | Not reused in any form beyond public general knowledge. |
| Repository inspection | Derivanta Engine `inspect` | INTEGRATE (tool run) | X | Run against PBD during qualification; results in M1 evidence. |
| Test assurance | Assertiva `audit` | INTEGRATE (tool run) | X | HIGH source-identity finding fixed in M0; state-after-rejection signals addressed. |
| QE strategy | QE Engineering `qe` CLI | INTEGRATE (tool run, deterministic mode) | X | Run in deterministic mode during qualification; results in M1 evidence. |
| Markdown link check | Derivanta `check_markdown_links.py` | REJECT (hard-coded root) | X | Original link test in PBD. |

## Comparative notes (no superiority claimed)
Static reading shows FTD and PBD share the stage/work-order design; PBD's reader quotes are verified, which FTD's catalog excerpts are not. HVE Core's quality rules are richer in platform-specific rendering; PBD's are enforced partly by runtime contracts. No benchmark comparing generated backlog quality across these tools has been executed; that belongs to M6.

## License recommendation (decision remains with the owner)
Apache-2.0 for PBD is compatible with the MIT and Apache-2.0 material adopted so far and with the owner's Apache-2.0 projects; it requires shipping the upstream license texts (done in `third_party/`) and preserving NOTICE files (none exist upstream). Material without a license (agile-story-skills) and Commons Clause code (Task Master) are not incorporated.
