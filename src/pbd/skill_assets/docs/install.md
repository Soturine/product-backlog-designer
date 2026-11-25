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
| `pbd start --source PATH=AUTHORITY ... --out DIR` | inventory, extraction, one reader assignment per source, work order |
| `pbd submit reading\|claims\|design\|review --file F` | all-or-nothing validation of an agent stage |
| `pbd finalize` | checks, verified gates, projections, exports, report.html |
| `pbd work-order` | what the next stage must account for |
| `pbd skill install` | install the skill folder for an agent host |
| `pbd doctor [--json]` | environment, host, skill locations, offline status |
| `pbd validate FILE` | schema + invariants + gate evidence rules for a canonical document |
| `pbd schema list\|show`, `pbd inventory`, `pbd id`, `pbd run`, `pbd privacy-scan` | utilities |

Exit codes: 0 ok, 1 invalid, 2 usage, 3 scope refusal. Audit, compare, refine, planning, ADR updates and publication are not implemented yet; see [roadmap](roadmap.md).
