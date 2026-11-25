# Install and use (pre-alpha)

Two separate things are installed:

1. **The runtime** — the `pbd` command (Python 3.11+, only dependency `jsonschema`). It validates, inventories, keeps state, verifies gates and renders. It never contacts a network service.
2. **The skill** — a folder with `SKILL.md`, the agent [procedures](../procedures/orchestrator.md), docs and the runtime source. An agent host (for example Claude Code) discovers the skill from this folder. Installing the Python package alone does not install the skill.

## Runtime
```sh
python -m venv .venv
# Windows PowerShell 5.1: .venv\Scripts\Activate.ps1      Unix: source .venv/bin/activate
python -m pip install -e .                # add ".[dev]" for tests, ".[browser]" for Playwright report tests
pbd doctor
```
Without installing, the agent can run `python -m pbd` with `PYTHONPATH=<skill folder>/src`.

## Skill
```sh
pbd skill install --scope project --project <your-project>   # → <project>/.claude/skills/product-backlog-designer/
pbd skill install --scope user                                # → ~/.claude/skills/product-backlog-designer/
```
Restart the agent session afterwards. Verified on 2026-11-24 with Claude Code 2.1.317: a new session in a sandbox project listed `product-backlog-designer` with its description. `pbd doctor` reports which locations contain the skill.

## Use
Ask in natural language, for example *"Gere o backlog completo a partir de docs/prd.md e prepare um pacote local para Azure DevOps Agile"*, or `/pbd`. The agent runs the stages; you do not chain commands. Output: `<artifact-root>/runs/<run>/output/report.html` plus JSON and requested exports.

## Commands
| Command | Purpose |
|---|---|
| `pbd start --source PATH=AUTHORITY ... --out DIR [--mode generate\|audit\|compare --baseline F] [--execution economical\|balanced\|rigorous]` | inventory, extraction, one reader assignment per source, work order |
| `pbd submit reading\|claims\|design\|review\|comparison --file F` | all-or-nothing validation of an agent stage |
| `pbd finalize` | checks, verified gates, projections, exports, report.html (or comparison outputs) |
| `pbd work-order` | what the next stage must account for |
| `pbd check`, `pbd clarify`, `pbd profile show\|infer\|execution` | structural health, decisions waiting, profiles |
| `pbd refine plan\|apply` | selective local refinement with diff and approval keys |
| `pbd plan [check]` | dependency order and sprint proposal; staleness check |
| `pbd evolve diff\|plan\|apply\|stale` | source diffs, decisions, lineage, invalidated artifacts |
| `pbd azure snapshot\|prepare\|approve\|apply\|verify` | local snapshots and the MOCK-only publication workflow |
| `pbd handoff ftd` | versioned handoff to Functional Test Designer |
| `pbd skill install` | install the skill folder for an agent host |
| `pbd doctor [--json]` | environment, host, skill locations, offline status |
| `pbd validate FILE` | schema + invariants + gate evidence rules for a canonical document |
| `pbd schema list\|show`, `pbd inventory`, `pbd id`, `pbd run`, `pbd privacy-scan` | utilities |

Exit codes: 0 ok, 1 invalid, 2 usage, 3 refusal. No command contacts a tracker; there is no live transport in this build.

## Hosts and portability
| Host | Install | Status |
|---|---|---|
| Claude Code | `pbd skill install --scope project\|user` (`.claude/skills/product-backlog-designer`) | discovery verified in a new session (2026-11-24) |
| Other agent hosts with a skills folder (for example Codex) | `pbd skill install --target <host skills folder>/product-backlog-designer` | not verified; the skill is plain Markdown + a Python CLI |
| Any agent without skill discovery | point the agent at `SKILL.md` in the installed folder or checkout | fallback; works wherever the agent can read files and run `pbd` |

The runtime is pure Python 3.11+ with one dependency (`jsonschema`); wheel and sdist both install outside a checkout and carry the schemas, profiles, locales, report assets and skill assets (verified 2026-11-25 in clean virtual environments on Windows). Linux was not exercised on this host (see the [ledger](../benchmarks/qualification-ledger.json), QL-008).

## Optional integrations
- **Azure DevOps:** local snapshots and a mock-only publication workflow ([azure](azure.md)). A live adapter does not exist.
- **Functional Test Designer:** `pbd handoff ftd` writes `ftd-handoff.json`; FTD reads the original sources itself ([handoff](../entrypoints/pbd.md)).
- **GitHub, Jira:** no adapter exists and none is claimed; the core never depends on a tracker.
- **Derivanta, Assertiva, QE Engineering:** used as development tools and design references only; nothing is merged into PBD.

## Troubleshooting
| Symptom | Cause and fix |
|---|---|
| `pbd: command not found` | activate the virtual environment, or run `python -m pbd` with `PYTHONPATH=<skill>/src` |
| `refused: ... unmapped work-item types` | pass `--type-map map.json` mapping native types to epic/feature/story/enabler/spike/bug/task |
| a submission is rejected | read every listed error: submissions are all-or-nothing and list all problems at once |
| G01 BLOCKED | a member was not read (unreadable, visual without transcription, extraction gaps); see Sources in the report |
| G13 BLOCKED | the review was not done by a separate agent (`sequential_role`) |
| `pbd plan` gives no sprints | no capacity was given; that is deliberate (no invented capacity) |
| `pbd evolve apply` refuses `all` | some changes overwrite human edits and need their own keys |
| Report opens without interactivity | JavaScript is disabled or blocked; all content is still shown |
