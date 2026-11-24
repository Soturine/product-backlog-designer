"""Remote-write authorization boundary (default deny).

No live transport exists in this implementation round. ``authorize_apply`` is the single
decision point any future transport must pass. It denies unless ALL hold:

* remote mode was explicitly opted into for this process (never by config file alone);
* the transport is a mock, or live transport has been separately enabled (it is not);
* the plan is approved, and the approval binds the exact plan digest and target namespace;
* the plan digest recomputed from its content matches (no edits after approval);
* the caller's target equals the approved target;
* no CONFLICT operations remain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pbd.core.canonical import digest

LIVE_TRANSPORT_AVAILABLE = False  # hard-coded for this round; no live adapter is shipped


class AuthorizationDenied(PermissionError):
    pass


@dataclass(frozen=True)
class RemoteAuthority:
    opted_in: bool = False
    transport: str = "none"  # none | mock | live


def plan_content_digest(plan: dict[str, Any]) -> str:
    body = {k: v for k, v in plan.items() if k not in ("plan_digest", "approval")}
    return digest(body)


def authorize_apply(plan: dict[str, Any], authority: RemoteAuthority, target_namespace: str) -> None:
    if not authority.opted_in or authority.transport == "none":
        raise AuthorizationDenied("remote operations are disabled (offline default)")
    if authority.transport == "live" and not LIVE_TRANSPORT_AVAILABLE:
        raise AuthorizationDenied("live transport is not available in this build")
    if authority.transport not in ("mock", "live"):
        raise AuthorizationDenied(f"unknown transport {authority.transport!r}")
    approval = plan.get("approval") or {}
    if approval.get("state") != "approved":
        raise AuthorizationDenied("plan is not approved")
    actual = plan_content_digest(plan)
    if plan.get("plan_digest") != actual:
        raise AuthorizationDenied("plan content changed after digest was computed (stale plan)")
    if approval.get("approved_plan_digest") != actual:
        raise AuthorizationDenied("approval does not match the current plan digest (stale approval)")
    approved_target = approval.get("approved_target_namespace")
    if approved_target != plan.get("target", {}).get("namespace") or approved_target != target_namespace:
        raise AuthorizationDenied("target does not match the approved target")
    if any(op.get("action") == "CONFLICT" for op in plan.get("operations", [])):
        raise AuthorizationDenied("plan contains unresolved conflicts")
