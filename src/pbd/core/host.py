"""Best-effort agent host and environment detection (read-only, no network).

Detection only reads environment variable *names/flags* and local paths; it never
prints environment values, which may contain secrets.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from pbd import SCHEMA_VERSION, __version__

# (host label, environment variable whose presence indicates it)
HOST_MARKERS: tuple[tuple[str, str], ...] = (
    ("claude-code", "CLAUDECODE"),
    ("codex", "CODEX_SANDBOX"),
    ("vscode-terminal", "VSCODE_PID"),
    ("github-actions", "GITHUB_ACTIONS"),
)
SKILL_DIR_NAME = "product-backlog-designer"


def detect_host(env: dict[str, str] | None = None) -> str:
    env = dict(os.environ) if env is None else env
    for label, marker in HOST_MARKERS:
        if env.get(marker):
            return label
    return "unknown"


def skill_locations(home: Path | None = None, project: Path | None = None) -> list[dict[str, Any]]:
    home = home or Path.home()
    project = project or Path.cwd()
    candidates = [
        ("project", project / ".claude" / "skills" / SKILL_DIR_NAME / "SKILL.md"),
        ("user", home / ".claude" / "skills" / SKILL_DIR_NAME / "SKILL.md"),
        ("user-agents", home / ".agents" / "skills" / SKILL_DIR_NAME / "SKILL.md"),
    ]
    return [{"scope": scope, "path": str(path), "present": path.is_file()} for scope, path in candidates]


def doctor(env: dict[str, str] | None = None) -> dict[str, Any]:
    py_ok = sys.version_info >= (3, 11)
    try:
        import jsonschema  # noqa: F401

        jsonschema_ok = True
    except ImportError:  # pragma: no cover
        jsonschema_ok = False
    return {
        "pbd_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "python": sys.version.split()[0],
        "python_supported": py_ok,
        "platform": f"{platform.system()} {platform.release()}",
        "host": detect_host(env),
        "dependencies": {"jsonschema": jsonschema_ok},
        "network_mode": "offline",
        "live_transport_available": False,
        "optional_tools": {
            "az_cli_on_path": shutil.which("az") is not None,
            "git_on_path": shutil.which("git") is not None,
        },
        "skill_installations": skill_locations(),
        "notes": [
            "Azure CLI presence is reported only; PBD never invokes it in this build.",
            "Semantic work (reading sources, designing, reviewing) is performed by the host agent.",
        ],
    }
