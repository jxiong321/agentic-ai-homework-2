"""Assignment 2, Part E: the diff of the plan against what ran. This file is yours.

"The one people skip" (Lecture 2, slide 54). The checker calls it on slide 51's run
in fixtures/traces/s49/, so keep this exact signature (checks/FORMATS.md, section
10.2):

    diff(plan, trace) -> {"steps": {step_id: label}, "extra": [step numbers]}

    steps   every plan step, labelled
              executed   it ran, in plan order
              skipped    it never ran
              reordered  it ran, out of plan order
    extra   the step numbers of tool_call lines that match no plan step

How a call matches a step is yours to decide: by its tool, and by any arguments
the plan fixes (an argument written "$fill" is fixed by nothing). Say how in your
report. Mind slide 51's run: it calls run_tests twice, and only one of those calls
can belong to each run_tests step.
"""

from __future__ import annotations

import json


def _matches_value(template, actual):
    if template == "$fill":
        return True
    if isinstance(template, dict):
        return isinstance(actual, dict) and all(
            k in actual and _matches_value(v, actual[k]) for k, v in template.items())
    if isinstance(template, list):
        return isinstance(actual, list) and len(template) == len(actual) and all(
            _matches_value(a, b) for a, b in zip(template, actual))
    return type(template) is type(actual) and template == actual


def _matches(step, call):
    if step.get("tool") != call.get("name"):
        return False
    try:
        args = json.loads(step["args_json"]) if "args_json" in step else step.get("args", {})
    except (ValueError, TypeError):
        return False
    return _matches_value(args, call.get("input", {}))


def match_calls(plan, trace):
    """Return (plan index or None, call) pairs in execution order.

    Explicit ids permit recorded retries; without ids each step consumes one
    matching call, with ambiguous candidates resolved in plan order.
    """
    steps = plan.get("steps", [])
    used = set()
    matches = []
    for call in trace:
        if call.get("type") != "tool_call":
            continue
        explicit = call.get("plan_step")
        candidates = [i for i, step in enumerate(steps)
                      if (step.get("id") == explicit if explicit is not None else i not in used)
                      and _matches(step, call)]
        index = candidates[0] if candidates else None
        if index is not None:
            used.add(index)
        matches.append((index, call))
    return matches


def diff(plan: dict, trace: list[dict]) -> dict:
    labels = {step["id"]: "skipped" for step in plan.get("steps", [])}
    extra = []
    highest = -1
    for index, call in match_calls(plan, trace):
        if index is None:
            extra.append(call["step"])
            continue
        step_id = plan["steps"][index]["id"]
        if index < highest:
            labels[step_id] = "reordered"
        elif labels[step_id] == "skipped":
            labels[step_id] = "executed"
        highest = max(highest, index)
    return {"steps": labels, "extra": extra}
