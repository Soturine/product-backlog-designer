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
    not_ready: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    sprint_of: dict[str, int] = {}
    load: dict[int, float] = defaultdict(float)
    unplanned: list[dict[str, str]] = []
    for iid in order:
        if iid in (not_ready or {}):
            # QL-019: blocked or deferred work is never placed in a sprint, even as a proposal
            unplanned.append({"item": iid, "reason": (not_ready or {})[iid]})
            continue
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
    errors = _validate_input(inp, items) + _validate_team(inp, items)
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
    # parent and child estimates are never added together: points live on stories, hours on leaves
    for item in work:
        iid = item["id"]
        if effort[iid] is None:
            continue
        if (
            effort_field == "story_points"
            and item["type"] == "task"
            and effort.get(item["parent"] or "") is not None
        ):
            effort[iid] = None
            provenance[iid]["effort"] = "task points not added to its story's points"
        kids = [w["id"] for w in work if w["parent"] == iid]
        if effort_field == "original_estimate" and any(effort.get(k) is not None for k in kids):
            effort[iid] = None
            provenance[iid]["effort"] = "parent hours not added: its tasks carry the hours"

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
    not_ready = _not_ready(items, backlog)
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
                "readiness": (items[i].get("readiness") or {}).get("status", "unassessed"),
                "backlog_position": tree_pos[i] + 1,
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
            "not_ready": [{"item": i, "reason": r} for i, r in sorted(not_ready.items())],
        },
        "sprints": None,
        "unplanned": [],
        "scenarios": [],
        "notes": [],
    }
    if inp.get("team"):
        result["team_plan"] = _team_plan(backlog, inp, deps, not_ready, use_proposed)
    if cycles:
        result["notes"].append(
            "dependency cycle: order falls back to the backlog tree; resolve the cycle first"
        )
    per = cap.get("per_sprint")
    if per:
        sprints, unplanned = _allocate(order, deps, effort, float(per), cap.get("sprints"), not_ready)
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
                order, deps, effort, float(sc["per_sprint"]), sc.get("sprints"), not_ready
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
    elif not inp.get("team"):
        result["notes"].append(
            "capacity unknown: this is a dependency-safe sequence, not a sprint plan; "
            "give capacity per sprint to allocate"
        )
    return result


# ------------------------------------------------------------------------------ team planning
RESPONSIBILITY = {"story_owner", "task_split", "whole_story_delegation"}
LEVELS3 = {"low", "medium", "high"}
STORY_TYPES = {"story", "enabler", "spike", "bug"}


def _validate_team(inp: dict[str, Any], items: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    team = inp.get("team")
    if team is None:
        return errors
    ids = set()
    for n, m in enumerate(team if isinstance(team, list) else []):
        if not isinstance(m, dict) or not str(m.get("id", "")).strip():
            errors.append(f"team[{n}]: id is required (as given by the user)")
            continue
        if m["id"] in ids:
            errors.append(f"team[{n}]: duplicate member {m['id']}")
        ids.add(m["id"])
        cap = m.get("capacity")
        if cap is not None:
            if not isinstance(cap, dict) or cap.get("unit") not in UNITS:
                errors.append(f"team[{n}].capacity.unit must be one of {sorted(UNITS)}")
            else:
                per = cap.get("per_sprint")
                values = per.values() if isinstance(per, dict) else [per]
                if any(not isinstance(v, int | float) or v < 0 for v in values):
                    errors.append(f"team[{n}].capacity.per_sprint must be a number >= 0 or a map by sprint")
    if not isinstance(team, list) or not team:
        errors.append("team must be a non-empty list of members supplied by the user")
    mode = inp.get("responsibility", "story_owner")
    if mode not in RESPONSIBILITY:
        errors.append(f"responsibility must be one of {sorted(RESPONSIBILITY)}")
    sprints = inp.get("sprints") or []
    indexes = [s.get("index") for s in sprints if isinstance(s, dict)]
    if len(indexes) != len(sprints) or any(not isinstance(i, int) or i < 1 for i in indexes):
        errors.append("sprints[].index must be positive integers")
    known = set(indexes)
    prop = inp.get("proposal") or {}
    actual = inp.get("actual") or {}
    for name, where in (("placement", prop), ("iterations", actual)):
        for iid, idx in (where.get(name) or {}).items():
            if iid not in items:
                errors.append(f"{name}: unknown item {iid}")
            elif idx not in known:
                errors.append(f"{name}: {iid} placed in undeclared sprint {idx}")
    for name, where in (("owners", prop), ("assignees", prop), ("assignees", actual)):
        for iid, member in (where.get(name) or {}).items():
            if iid not in items:
                errors.append(f"{name}: unknown item {iid}")
            elif member not in ids:
                errors.append(
                    f"{name}: {iid} assigned to unknown member {member!r} (members come from the user)"
                )
            elif name == "owners" and items[iid]["type"] not in STORY_TYPES:
                errors.append(f"owners: {iid} is a {items[iid]['type']}; owners are accountable for stories")
    for iid, a in (inp.get("assessments") or {}).items():
        if iid not in items:
            errors.append(f"assessments: unknown item {iid}")
            continue
        bad = [k for k in ("complexity", "risk", "confidence") if k in a and a[k] not in LEVELS3]
        if bad or not str(a.get("rationale", "")).strip():
            errors.append(f"assessments: {iid} needs low/medium/high values and a rationale")
    return errors


def _member_capacity(member: dict[str, Any], sprint: int) -> tuple[float | None, str | None]:
    cap = member.get("capacity") or {}
    per = cap.get("per_sprint")
    value = per.get(str(sprint), per.get(sprint)) if isinstance(per, dict) else per
    return (float(value) if isinstance(value, int | float) else None), cap.get("unit")


def _team_plan(
    backlog: dict[str, Any],
    inp: dict[str, Any],
    deps: dict[str, set[str]],
    not_ready: dict[str, str],
    use_proposed: bool,
) -> dict[str, Any]:
    """Owner/assignee view of an agent-proposed placement, checked deterministically.

    The runtime never decides who does what or when: placement, owners and assignees come from
    the planning proposal (written by the agent from the user's request) or from an explicitly
    supplied snapshot (actual). It checks references, blocked work, dependency order, capacity per
    person in matching units, and keeps actual, proposed and derived assignments apart.
    """
    items = {i["id"]: i for i in backlog["items"]}
    team = {m["id"]: m for m in inp["team"]}
    mode = inp.get("responsibility", "story_owner")
    prop, actual = inp.get("proposal") or {}, inp.get("actual") or {}
    placement: dict[str, int] = dict(prop.get("placement") or {})
    owners: dict[str, str] = dict(prop.get("owners") or {})
    p_assign: dict[str, str] = dict(prop.get("assignees") or {})
    a_assign: dict[str, str] = dict(actual.get("assignees") or {})
    rationale = prop.get("rationale") or {}
    sprints_in = sorted(inp.get("sprints") or [], key=lambda s: s["index"])
    children: dict[str, list[str]] = defaultdict(list)
    for i in backlog["items"]:
        if i["parent"]:
            children[i["parent"]].append(i["id"])
    stories = [i for i in tree_order(backlog) if i["type"] in STORY_TYPES]
    violations: list[str] = []
    notes: list[str] = []

    def task_sprint(tid: str) -> int | None:
        if tid in placement:
            return placement[tid]
        parent = items[tid]["parent"]
        return placement.get(parent) if parent else None

    def assignee(tid: str) -> tuple[str | None, str]:
        """(member, provenance) - proposal first, then derived delegation, then the actual snapshot."""
        if tid in p_assign:
            return p_assign[tid], "proposed"
        parent = items[tid]["parent"]
        if mode == "whole_story_delegation" and parent in owners:
            return owners[parent], "derived_delegation"
        if tid in a_assign:
            return a_assign[tid], "actual"
        return None, "none"

    story_rows: list[dict[str, Any]] = []
    for s in stories:
        sid = s["id"]
        tasks = [t for t in children.get(sid, []) if items[t]["type"] == "task"]
        if mode in ("story_owner", "whole_story_delegation") and sid in placement and sid not in owners:
            violations.append(f"{sid}: placed without the accountable owner the request asks for")
        rows: list[dict[str, Any]] = []
        for tid in tasks:
            who, how = assignee(tid)
            est, est_prov = _value(items[tid], "original_estimate", use_proposed)
            ts = task_sprint(tid)
            row: dict[str, Any] = {
                "task": tid,
                "sprint": ts,
                "assignee": who,
                "assignee_provenance": how,
                "actual_assignee": a_assign.get(tid),
                "estimate_hours": est if isinstance(est, int | float) else None,
                "estimate_provenance": est_prov,
            }
            if a_assign.get(tid) and who and a_assign[tid] != who:
                row["discrepancy"] = "proposal differs from the actual assignee in the snapshot"
            if mode == "story_owner" and who and owners.get(sid) and who != owners[sid]:
                row["collaborator"] = True  # owner stays accountable; the task assignee is a collaborator
            if sid in placement and ts is not None:
                if ts < placement[sid]:
                    row["timing"] = "preparation"
                elif ts > placement[sid]:
                    row["timing"] = "carryover"
            rows.append(row)
        sp, sp_prov = _value(s, "story_points", use_proposed)
        story_rows.append(
            {
                "story": sid,
                "sprint": placement.get(sid),
                "owner": owners.get(sid),
                "owner_provenance": "proposed"
                if sid in owners
                else ("actual" if sid in a_assign else "none"),
                "actual_owner": a_assign.get(sid),
                "story_points": sp if isinstance(sp, int | float) else None,
                "story_points_provenance": sp_prov,
                "tasks": rows,
                "rationale": rationale.get(sid),
            }
        )
    # blocked work, dependency order
    for iid, idx in sorted(placement.items()):
        if iid in not_ready:
            violations.append(f"{iid}: placed in sprint {idx} but {not_ready[iid]}")
        for d in sorted(deps.get(iid, set())):
            dsprint = placement.get(d, task_sprint(d) if items.get(d, {}).get("type") == "task" else None)
            if dsprint is None:
                violations.append(f"{iid}: waits for {d}, which is not placed")
            elif dsprint > idx:
                violations.append(
                    f"{iid}: placed in sprint {idx} before its predecessor {d} (sprint {dsprint})"
                )
    # per-person load in the member's own unit; parents and children never summed together
    people = []
    for idx in [s["index"] for s in sprints_in]:
        for mid, member in team.items():
            cap, unit = _member_capacity(member, idx)
            load = 0.0
            counted: list[str] = []
            unknown: list[str] = []
            mismatch: list[str] = []
            if unit == "story_points":
                for row in story_rows:
                    if row["sprint"] == idx and row["owner"] == mid:
                        if row["story_points"] is None:
                            unknown.append(row["story"])
                        else:
                            load += row["story_points"]
                            counted.append(row["story"])
            else:
                for row in story_rows:
                    for t in row["tasks"]:
                        if t["sprint"] != idx or t["assignee"] != mid:
                            continue
                        if t["estimate_hours"] is None:
                            pts, _ = _value(items[t["task"]], "story_points", use_proposed)
                            (mismatch if isinstance(pts, int | float) else unknown).append(t["task"])
                        else:
                            load += t["estimate_hours"]
                            counted.append(t["task"])
            entry: dict[str, Any] = {
                "member": mid,
                "sprint": idx,
                "unit": unit,
                "capacity": cap,
                "load": load if counted else (0 if not (unknown or mismatch) else None),
                "remaining": (cap - load) if cap is not None and not unknown and not mismatch else None,
                "counted": counted,
                "unknown_estimates": unknown,
                "unit_mismatch": mismatch,
            }
            if unit is None:
                entry["remaining"] = None
            if cap is not None and load > cap:
                violations.append(f"{mid}: sprint {idx} load {load:g} exceeds capacity {cap:g} {unit}")
            people.append(entry)
    unassigned = [
        t["task"]
        for row in story_rows
        for t in row["tasks"]
        if t["assignee"] is None and t["sprint"] is not None
    ]
    unallocated = [
        {"item": row["story"], "reason": not_ready.get(row["story"], "not placed by the proposal")}
        for row in story_rows
        if row["sprint"] is None
    ]
    incomplete = [p for p in people if p["unknown_estimates"] or p["unit_mismatch"] or p["capacity"] is None]
    if violations:
        g10 = {"status": "FAIL", "reason": "; ".join(violations[:6])}
    elif not placement:
        g10 = {"status": "NOT_RUN", "reason": "no placement proposed: owners only, no sprint allocation"}
    elif incomplete:
        g10 = {
            "status": "BLOCKED",
            "reason": "capacity cannot be verified: unknown estimates, unit mismatches or unknown capacity "
            f"for {sorted({p['member'] for p in incomplete})}",
        }
    else:
        g10 = {
            "status": "PASS",
            "reason": "placement respects readiness, dependencies and per-person capacity",
        }
    if mode == "whole_story_delegation":
        notes.append(
            "whole-story delegation is a proposal: child tasks follow the owner here, but a tracker never "
            "changes child assignments because a parent is assigned"
        )
    return {
        "mode": mode,
        "members": [{k: m[k] for k in ("id", "name", "skills", "capacity") if k in m} for m in inp["team"]],
        "sprints": [
            {
                **{k: s[k] for k in ("index", "goal", "start", "end", "working_days") if k in s},
                "stories": [r["story"] for r in story_rows if r["sprint"] == s["index"]],
            }
            for s in sprints_in
        ],
        "stories": story_rows,
        "people": people,
        "unassigned_tasks": unassigned,
        "unallocated": unallocated,
        "assessments": inp.get("assessments") or {},
        "actual_source": actual.get("source"),
        "violations": violations,
        "g10": g10,
        "notes": notes,
    }


def _not_ready(items: dict[str, dict[str, Any]], backlog: dict[str, Any]) -> dict[str, str]:
    """Work the backlog itself declares blocked or deferred, with the typed blockers it cites."""
    keys = backlog.get("keys") or {}
    out = {}
    for iid, item in items.items():
        rd = item.get("readiness") or {}
        if rd.get("status") in ("blocked", "deferred"):
            refs = [keys.get(b["ref"], b["ref"]) for b in rd.get("blocked_by", [])]
            out[iid] = f"{rd['status']}" + (f" by {refs}" if refs else "") + f": {rd.get('rationale', '')}"
    return out


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
