"""Assignment 2, Part E: three detectors, and Lecture 2's ladder. This file is yours.

Three of the four plan failures have a detector of a few lines over a trace
(Lecture 2, slides 45 to 49); the validator is the fourth. The checker calls these
on fixtures/traces/, so keep these exact signatures (checks/FORMATS.md, section
10.2):

    repeat_check(trace) -> list[list]
        Circular reasoning. Exact repeats: two tool_call lines with the same tool
        and the same arguments. Returns each group of repeats as the step numbers
        of its tool_call lines, e.g. [[1, 3], [2, 4]].

    orphan_check(plan) -> list
        Hallucinated steps. The ids of steps, other than the last, whose result no
        later step uses: no later step lists them in depends_on.

    expected_result_check(plan, trace) -> list
        Premature stopping, in part. The ids of plan steps that did not run and
        return their result. It catches skipped steps, not a plan too short.

    ladder(plan, trace) -> {"q1": {"fired": bool, "ids": [...]}, "q2": ..., "q3": ...}
        Lecture 2's questions 1 to 3 (slide 50), in order: did any two steps do
        the same thing; is any step's result never used; did every planned step
        execute. "ids" says what fired: groups of step numbers for q1, step ids
        (or, from a trace, step numbers) for q2 and q3. Question 4 needs
        judgment, so it goes in your report, not here.

    plan    a plan (section 10.1)
    trace   a list of trace lines, as harness.trace.read_trace returns them

A plan with no depends_on cannot answer question 2 from the plan. Answer it from
the trace, and say how in your report.
"""

from __future__ import annotations

import json
from agent.diff import match_calls


def repeat_check(trace: list[dict]) -> list[list]:
    groups = {}
    for call in trace:
        if call.get("type") == "tool_call":
            key = (call.get("name"), json.dumps(call.get("input", {}), sort_keys=True))
            groups.setdefault(key, []).append(call["step"])
    return [group for group in groups.values() if len(group) > 1]


def orphan_check(plan: dict) -> list:
    steps = plan.get("steps", [])
    return [step["id"] for i, step in enumerate(steps[:-1])
            if not any(step["id"] in later.get("depends_on", []) for later in steps[i + 1:])]


def expected_result_check(plan: dict, trace: list[dict]) -> list:
    succeeded = {index for index, call in match_calls(plan, trace)
                 if index is not None and not call.get("is_error", False)}
    return [step["id"] for index, step in enumerate(plan.get("steps", []))
            if index not in succeeded]


def ladder(plan: dict, trace: list[dict]) -> dict:
    repeats = repeat_check(trace)
    if all("depends_on" in step for step in plan.get("steps", [])):
        unused = orphan_check(plan)
    else:
        # In incomplete historical traces this is a redundancy heuristic, not
        # proof of data flow: flag later exact repeats with the same recorded result.
        calls = {call["step"]: call for call in trace if call.get("type") == "tool_call"}
        unused = [turn for group in repeats for turn in group[1:]
                  if calls[turn].get("result_excerpt") == calls[group[0]].get("result_excerpt")
                  and calls[turn].get("result_chars") == calls[group[0]].get("result_chars")]
    missing = expected_result_check(plan, trace)
    return {key: {"fired": bool(ids), "ids": ids}
            for key, ids in (("q1", repeats), ("q2", unused), ("q3", missing))}


if __name__ == "__main__":
    raise SystemExit("Assignment 2 Part E: print both runs' ladders here, if you like")
