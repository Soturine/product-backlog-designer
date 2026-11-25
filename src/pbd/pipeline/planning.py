"""Planning engine: dependency order, prioritisation and sprint proposals from evidence and choices.

Inputs are the canonical backlog and an optional planning file written or confirmed by the user:

```json
{"capacity": {"unit": "story_points", "per_sprint": 20, "sprints": 4},
 "calendar": {"start": "2027-01-04", "sprint_days": 14},
 "technique": "wsjf",            # none | moscow | rice | wsjf
 "technique_inputs": {"PBD-STORY-...": {"moscow": "must"}},
 "teams": {"PBD-STORY-...": "team-a"},
 "use_proposed_estimates": false,
 "scenarios": [{"name": "lower capacity", "per_sprint": 15}]}
```

Rules: nothing is invented. Zero is a value, absence is unknown. Only confirmed field values count
(proposed ones only when the user says so, and they are labelled). Units are never converted
(points are not hours). Without a known capacity there is a dependency-safe sequence, never a
sprint promise; without a calendar there are no dates. Scores are computed only when every input
of the formula is present; otherwise the item is listed with the missing inputs. Every output is a
proposal (``committed: false``) bound to the backlog digest; a changed backlog makes it stale.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
from typing import Any

from pbd.core.canonical import digest
from pbd.render.exports import tree_order

UNITS = {"story_points": "story_points", "hours": "original_estimate"}
TECHNIQUES = {"none", "moscow", "rice", "wsjf"}
MOSCOW = {"must": 0, "should": 1, "could": 2, "wont": 3}
DEPENDENCY_TYPES = {"predecessor", "external_blocker"}


class PlanningError(ValueError):
    def __init__(self, message: str, errors: list[str]) -> None:
        super().__init__(message + "".join(f"\n  - {e}" for e in errors))
        self.errors = errors


def _value(item: dict[str, Any], name: str, use_proposed: bool) -> tuple[Any, str]:
    """(value, provenance) where provenance is confirmed | proposed | absent | unknown."""
    fv = (item.get("fields") or {}).get(name)
    if not isinstance(fv, dict):
        return None, "absent"
    state = fv.get("state")
    if state == "confirmed" and "value" in fv:
        return fv["value"], "confirmed"
    if state == "proposed" and "value" in fv and use_proposed:
        return fv["value"], "proposed"
    if state in ("unknown", "unset", "unavailable"):
        return None, "unknown"
    return None, "absent" if state != "proposed" else "proposed_not_used"


def _validate_input(inp: dict[str, Any], items: dict[str, Any]) -> list[str]:
    errors = []
    cap = inp.get("capacity") or {}
    if cap:
        if cap.get("unit") not in UNITS:
            errors.append(f"capacity.unit must be one of {sorted(UNITS)}")
        per = cap.get("per_sprint")
        if per is not None and (not isinstance(per, int | float) or per <= 0):
            errors.append("capacity.per_sprint must be a positive number (zero capacity cannot hold work)")
        sprints = cap.get("sprints")
        if sprints is not None and (not isinstance(sprints, int) or sprints < 1):
            errors.append("capacity.sprints must be a positive integer")
    cal = inp.get("calendar") or {}
    if cal:
        try:
            dt.date.fromisoformat(str(cal.get("start")))
        except ValueError:
            errors.append("calendar.start must be an ISO date")
        if not isinstance(cal.get("sprint_days"), int) or cal["sprint_days"] < 1:
            errors.append("calendar.sprint_days must be a positive integer")
        if not cap.get("per_sprint"):
            errors.append(
                "a calendar needs a known capacity per sprint (dates are never promised without it)"
            )
    tech = inp.get("technique", "none")
    if tech not in TECHNIQUES:
        errors.append(f"technique must be one of {sorted(TECHNIQUES)}")
    for key in (inp.get("technique_inputs") or {}) | (inp.get("teams") or {}):
        if key not in items:
            errors.append(f"unknown item {key} in planning input")
    for key, vals in (inp.get("technique_inputs") or {}).items():
        if "moscow" in vals and vals["moscow"] not in MOSCOW:
            errors.append(f"{key}: moscow must be one of {sorted(MOSCOW)}")
    return errors


def _graph(backlog: dict[str, Any]) -> tuple[dict[str, set[str]], list[dict[str, Any]], list[str]]:
    """predecessor graph (item -> items it waits for), external blockers, invalid relations."""
    items = {i["id"] for i in backlog["items"]}
    deps: dict[str, set[str]] = {i: set() for i in items}
    blockers, invalid = [], []
    for rel in backlog["relations"]:
        if rel["type"] not in DEPENDENCY_TYPES or rel["status"] == "rejected":
            continue
        if rel["type"] == "external_blocker":
            if rel["source"] in items:
                blockers.append(
                    {
                        "item": rel["source"],
                        "blocker": rel["target"],
                        "reason": rel["reason"],
                        "status": rel["status"],
                    }
                )
            continue
        src, tgt = rel["source"], rel["target"]
        if src not in items or not isinstance(tgt, str) or tgt not in items:
            invalid.append(f"{rel['id']}: predecessor between unknown items")
        elif src == tgt:
            invalid.append(f"{rel['id']}: an item cannot precede itself")
        else:
            deps[tgt].add(src)  # source must come before target
    return deps, blockers, invalid


def _scores(
    items: list[dict[str, Any]], technique: str, inputs: dict[str, Any], use_proposed: bool, effort_field: str
) -> tuple[dict[str, float | int], dict[str, list[str]]]:
    scores: dict[str, float | int] = {}
    missing: dict[str, list[str]] = {}
    for item in items:
        iid = item["id"]
        given = inputs.get(iid, {})
        if technique == "moscow":
            if "moscow" in given:
                scores[iid] = MOSCOW[given["moscow"]]
            else:
                missing[iid] = ["moscow category (user choice)"]
        elif technique == "wsjf":
            parts = {}
            for name in ("business_value", "time_criticality", "risk"):
                value, _ = _value(item, name, use_proposed)
                if name == "risk" and "risk_reduction" in given:
                    value = given["risk_reduction"]
                if isinstance(value, int | float):
                    parts[name] = value
            size, _ = _value(item, effort_field, use_proposed)
            need = [n for n in ("business_value", "time_criticality", "risk") if n not in parts]
            if not isinstance(size, int | float) or size <= 0:
                need.append(f"job size ({effort_field} > 0)")
            if need:
                missing[iid] = need
            else:
                assert isinstance(size, int | float)
                scores[iid] = round(sum(parts.values()) / size, 4)
        elif technique == "rice":
            need = [
                n
                for n in ("reach", "impact", "confidence", "effort")
                if not isinstance(given.get(n), int | float)
            ]
            if not need and given["effort"] <= 0:
                need = ["effort > 0"]
            if need:
                missing[iid] = need
            else:
                scores[iid] = round(
                    given["reach"] * given["impact"] * given["confidence"] / given["effort"], 4
                )
    return scores, missing


def _allocate(
    order: list[str],
    deps: dict[str, set[str]],
    effort: dict[str, float | int | None],
    per_sprint: float,
    sprints: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    sprint_of: dict[str, int] = {}
    load: dict[int, float] = defaultdict(float)
    unplanned: list[dict[str, str]] = []
    for iid in order:
        size = effort.get(iid)
        if size is None:
            unplanned.append({"item": iid, "reason": "estimate unknown"})
            continue
        if size > per_sprint:
            unplanned.append(
                {"item": iid, "reason": f"estimate {size} exceeds sprint capacity {per_sprint}: split needed"}
            )
            continue
        blocked = [d for d in deps[iid] if d not in sprint_of]
        if blocked:
            unplanned.append({"item": iid, "reason": f"waits for unplanned predecessors {sorted(blocked)}"})
            continue
        start = max((sprint_of[d] + 1 for d in deps[iid]), default=0)  # successors start after
        n = start
        while load[n] + size > per_sprint:
            n += 1
        if sprints is not None and n >= sprints:
            unplanned.append({"item": iid, "reason": f"does not fit in the {sprints} sprints given"})
            continue
        sprint_of[iid] = n
        load[n] += size
    count = max(sprint_of.values(), default=-1) + 1
    out = [
        {
            "index": n + 1,
            "items": [i for i in order if sprint_of.get(i) == n],
            "load": load[n],
            "capacity": per_sprint,
            "utilization": round(load[n] / per_sprint, 3),
        }
        for n in range(count)
    ]
    return out, unplanned


def plan(backlog: dict[str, Any], inp: dict[str, Any] | None = None) -> dict[str, Any]:
    inp = dict(inp or {})
    items = {i["id"]: i for i in backlog["items"]}
    errors = _validate_input(inp, items)
    if errors:
        raise PlanningError("planning input rejected", errors)
    use_proposed = bool(inp.get("use_proposed_estimates"))
    cap = inp.get("capacity") or {}
    unit = cap.get("unit", "story_points")
    effort_field = UNITS[unit]
    deps, blockers, invalid = _graph(backlog)
    cycles: list[str] = []
    try:
        topo = list(TopologicalSorter({k: v for k, v in deps.items()}).static_order())
    except CycleError as exc:
        cycles = [str(x) for x in exc.args[1]] if len(exc.args) > 1 else ["cycle"]
        topo = [i["id"] for i in tree_order(backlog)]
    tree_pos = {i["id"]: n for n, i in enumerate(tree_order(backlog))}
    work = [items[i] for i in topo if items[i]["type"] not in ("epic", "feature")]
    technique = inp.get("technique", "none")
    scores, missing = _scores(work, technique, inp.get("technique_inputs") or {}, use_proposed, effort_field)
    priority: dict[str, Any] = {}
    effort: dict[str, float | int | None] = {}
    provenance: dict[str, dict[str, str]] = {}
    other_unit = "original_estimate" if effort_field == "story_points" else "story_points"
    for item in work:
        pv, pprov = _value(item, "priority", use_proposed)
        ev, eprov = _value(item, effort_field, use_proposed)
        ov, _ = _value(item, other_unit, use_proposed)
        priority[item["id"]] = pv
        effort[item["id"]] = ev if isinstance(ev, int | float) else None
        provenance[item["id"]] = {"priority": pprov, "effort": eprov}
        if effort[item["id"]] is None and isinstance(ov, int | float):
            provenance[item["id"]]["effort"] = f"only {other_unit} given (units are not converted)"

    def rank(iid: str) -> tuple[Any, ...]:
        s = scores.get(iid)
        tech_key = (s is None, (s if technique == "moscow" else -(s or 0)) if s is not None else 0)
        p = priority.get(iid)
        return (*tech_key, p is None, p if isinstance(p, int | float) else 0, tree_pos[iid])

    order = []
    ready = {i["id"] for i in work}
    placed: set[str] = set()
    pending = sorted(ready, key=rank)
    while pending:
        nxt = next((i for i in pending if deps[i] & ready <= placed), pending[0])
        order.append(nxt)
        placed.add(nxt)
        pending.remove(nxt)
    teams = inp.get("teams") or {}
    cross = [
        {"item": i, "team": teams[i], "waits_for": d, "other_team": teams[d]}
        for i in order
        for d in sorted(deps[i])
        if i in teams and d in teams and teams[i] != teams[d]
    ]
    result: dict[str, Any] = {
        "kind": "pbd.sprint-plan",
        "backlog_digest": digest({k: v for k, v in backlog.items() if k not in ("keys", "_digest")}),
        "input_digest": digest(inp),
        "committed": False,
        "status": "proposal",
        "inputs": {
            "capacity": cap or None,
            "calendar": inp.get("calendar") or None,
            "technique": technique,
            "use_proposed_estimates": use_proposed,
            "unit": unit,
        },
        "sequence": [
            {
                "item": i,
                "type": items[i]["type"],
                "title": items[i]["title"],
                "priority": priority.get(i),
                "effort": effort.get(i),
                "provenance": provenance[i],
                "score": scores.get(i),
                "waits_for": sorted(deps[i]),
            }
            for i in order
        ],
        "score_missing_inputs": missing,
        "checks": {
            "cycles": cycles,
            "invalid_relations": invalid,
            "external_blockers": blockers,
            "cross_team_dependencies": cross,
            "unknown_estimates": [i for i in order if effort.get(i) is None],
            "zero_estimates": [i for i in order if effort.get(i) == 0],
        },
        "sprints": None,
        "unplanned": [],
        "scenarios": [],
        "notes": [],
    }
    if cycles:
        result["notes"].append(
            "dependency cycle: order falls back to the backlog tree; resolve the cycle first"
        )
    per = cap.get("per_sprint")
    if per:
        sprints, unplanned = _allocate(order, deps, effort, float(per), cap.get("sprints"))
        result["sprints"] = sprints
        result["unplanned"] = unplanned
        cal = inp.get("calendar") or {}
        if cal:
            start = dt.date.fromisoformat(str(cal["start"]))
            for s in sprints:
                begin = start + dt.timedelta(days=cal["sprint_days"] * (s["index"] - 1))
                s["dates"] = {
                    "start": begin.isoformat(),
                    "end": (begin + dt.timedelta(days=cal["sprint_days"] - 1)).isoformat(),
                    "derived_from": "user calendar",
                }
        for sc in inp.get("scenarios") or []:
            if not isinstance(sc.get("per_sprint"), int | float) or sc["per_sprint"] <= 0:
                continue
            s_sprints, s_unplanned = _allocate(
                order, deps, effort, float(sc["per_sprint"]), sc.get("sprints")
            )
            result["scenarios"].append(
                {
                    "name": str(sc.get("name", "scenario")),
                    "per_sprint": sc["per_sprint"],
                    "sprints": len(s_sprints),
                    "unplanned": len(s_unplanned),
                    "committed": False,
                }
            )
    else:
        result["notes"].append(
            "capacity unknown: this is a dependency-safe sequence, not a sprint plan; "
            "give capacity per sprint to allocate"
        )
    return result


def is_stale(plan_doc: dict[str, Any], backlog: dict[str, Any]) -> bool:
    return plan_doc.get("backlog_digest") != digest(
        {k: v for k, v in backlog.items() if k not in ("keys", "_digest")}
    )


def plan_markdown(doc: dict[str, Any]) -> str:
    lines = ["# Sprint plan (proposal — not committed)", ""]
    lines += [f"- {n}" for n in doc["notes"]]
    if doc["sprints"]:
        for s in doc["sprints"]:
            dates = f" ({s['dates']['start']} – {s['dates']['end']})" if s.get("dates") else ""
            lines += ["", f"## Sprint {s['index']}{dates} — {s['load']}/{s['capacity']}"]
            titles = {x["item"]: x["title"] for x in doc["sequence"]}
            lines += [f"- {titles[i]}" for i in s["items"]]
    else:
        lines += ["", "## Sequence"] + [f"{n + 1}. {x['title']}" for n, x in enumerate(doc["sequence"])]
    if doc["unplanned"]:
        lines += ["", "## Not planned"] + [f"- {u['item']}: {u['reason']}" for u in doc["unplanned"]]
    return "\n".join(lines) + "\n"
