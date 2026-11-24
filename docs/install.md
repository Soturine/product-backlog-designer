# Install and host detection (pre-alpha)

The skill works without the runtime: the agent follows [SKILL.md](../SKILL.md). The `pbd` runtime adds deterministic validation, inventory and state. It never contacts a network service.

## Runtime
```sh
python -m venv .venv
# Windows PowerShell 5.1: .venv\Scripts\Activate.ps1   Unix: source .venv/bin/activate
python -m pip install -e ".[dev]"
pbd --help
pbd doctor
```
Requires Python 3.11+. The only runtime dependency is `jsonschema`. Run tests with `python -m pytest`.

## Skill installation
Copy or link the repository folder so that `SKILL.md` is at one of:
- project: `.claude/skills/product-backlog-designer/SKILL.md`
- user: `~/.claude/skills/product-backlog-designer/SKILL.md`

`pbd doctor` reports which locations contain the skill and the detected agent host (from environment markers only, never values). No configuration wizard is required.

## Commands available in M0
| Command | Purpose |
|---|---|
| `pbd doctor [--json]` | environment, host, skill locations, offline status |
| `pbd schema list` / `show NAME` | bundled canonical schemas |
| `pbd validate FILE` | schema + referential invariants + gate evidence rules |
| `pbd inventory --source PATH=AUTHORITY` | safe source inventory with member ledger (not reading) |
| `pbd id KIND` | mint opaque stable identifiers |
| `pbd run init` / `status` | private run manifest and journal under `.pbd/` |
| `pbd privacy-scan PATH` | secrets, personal e-mails, private tracker URLs |

Exit codes: 0 ok, 1 invalid, 2 usage, 3 scope refusal. Generation, rendering, audit and Azure packaging are not implemented yet; see [roadmap](roadmap.md).
