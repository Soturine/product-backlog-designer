"""Portable execution profiles: how the orchestrator spends agents, never which vendor model to call.

Roles are logical (reader per source, orchestrator, designer, reviewer). A profile says how many
physical agents may run at once, which capability tier each role needs and whether independence
is required. The host maps tiers to the models it actually has; the run records the model that
really ran. A sequential fallback is always allowed but is recorded as reduced independence (G13
cannot PASS on a declaration alone).
"""

from __future__ import annotations

from typing import Any

TIERS = ("economy", "standard", "strong")

PROFILES: dict[str, dict[str, Any]] = {
    "economical": {
        "summary": "Lowest cost: few concurrent agents, cheapest capable tier, context reused where safe.",
        "max_concurrent_agents": 1,
        "tiers": {
            "reader": "economy",
            "orchestrator": "economy",
            "designer": "standard",
            "reviewer": "standard",
        },
        "delegate_readers": "only_when_more_than_one_source",
        "independent_review": "preferred",
        "reuse_context": True,
    },
    "balanced": {
        "summary": "Delegates readers and the reviewer when useful; standard tiers for interpretation.",
        "max_concurrent_agents": 2,
        "tiers": {
            "reader": "economy",
            "orchestrator": "standard",
            "designer": "standard",
            "reviewer": "standard",
        },
        "delegate_readers": "per_source",
        "independent_review": "required",
        "reuse_context": True,
    },
    "rigorous": {
        "summary": "Independent reviewer on a strong tier, fresh context per role, readers per source.",
        "max_concurrent_agents": 3,
        "tiers": {
            "reader": "standard",
            "orchestrator": "standard",
            "designer": "strong",
            "reviewer": "strong",
        },
        "delegate_readers": "per_source",
        "independent_review": "required",
        "reuse_context": False,
    },
}
DEFAULT = "balanced"


def execution_profile(name: str | None) -> dict[str, Any]:
    key = name or DEFAULT
    if key not in PROFILES:
        raise ValueError(f"unknown execution profile {key!r}; choose from {sorted(PROFILES)}")
    return {
        "id": key,
        **PROFILES[key],
        "fallback": (
            "If the host cannot start separate agents, run roles sequentially, record "
            "independence=sequential_role and report reduced independence; never claim separate_agent."
        ),
        "models": "Use the host's cheapest model that meets each tier; record the model that actually ran.",
    }
