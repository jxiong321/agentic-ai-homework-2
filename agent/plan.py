"""Assignment 2, Parts A and C: the planner and the reviser. This file is yours.

The contract (checks/FORMATS.md, section 10). The checker calls both functions
directly, with a scripted model that keeps a copy of every request, so keep these
exact signatures. You may add keyword arguments with defaults; the checker passes
only these.

    make_plan(client, issue_number, tool_schemas, trace=None) -> dict
    revise_plan(client, plan, step_results, trace=None) -> dict

    client        harness.client.ModelClient: client.create(system=, messages=, tools=)
    issue_number  the issue to triage, an int
    tool_schemas  the tool definitions, as ctx.tools.schemas gives them
    plan          the active plan, its steps' statuses brought up to date
    step_results  one entry per step that has run (section 10.3)
    trace         a harness.trace.TraceWriter, or None. When you get one, trace your
                  model call: trace.model_call(0, response, purpose="plan") in
                  make_plan, purpose="revise" in revise_plan
    returns       a plan (section 10.1): {"meta": {...}, "steps": [...]}

make_plan writes the plan and stops (Lecture 2, slide 15). Its request carries the
task, the issue number and the tool list, and nothing from the issue: not its body,
not its title. The checker looks for each issue's sentinel string in every request.
The usual way to get the plan back as data: offer the model one tool whose
input_schema is agent/plan_schema.json, and read the plan from its call. Mark an
argument that waits on an earlier step's result "$fill"; the executor fills it in.

revise_plan repairs before it replaces: it never changes a step whose status is
done; it may change a step that failed, to retry it, and any step not yet run. A
step whose step result says "done" comes back unchanged, every field but status,
whatever the model wrote. Its request carries structured step results only (status, counts, paths,
error codes): never the issue's text, and never a step result's `args`, which the
executor may have filled in from the issue.

Keep your prompts in prompts/.
"""

from __future__ import annotations

import copy
import json

from harness import ROOT


def make_plan(client, issue_number: int, tool_schemas: list[dict], trace=None) -> dict:
    """Request one plan without fetching issue content or executing its steps.

    An absent or ambiguous plan call returns a schema-invalid object so Part B
    can reject it through the same bounded path as other invalid plans.
    """
    prompt_path = "prompts/planner.md"
    schema = json.loads((ROOT / "agent/plan_schema.json").read_text())
    response = client.create(
        system=(ROOT / prompt_path).read_text(),
        messages=[{
            "role": "user",
            "content": f"Plan the triage of issue #{issue_number}.\n"
                       "Available execution tool definitions:\n"
                       + json.dumps(tool_schemas),
        }],
        tools=[{
            "name": "submit_plan",
            "description": "Return a proposed triage plan as data; execute nothing.",
            "input_schema": schema,
            "strict": True,
        }],
    )
    if trace is not None:
        trace.model_call(0, response, purpose="plan")
    calls = response.tool_calls
    if (len(calls) != 1 or calls[0].name != "submit_plan"
            or not isinstance(calls[0].input, dict)):
        plan = {}
    else:
        plan = copy.deepcopy(calls[0].input)
    # Provenance comes from our code and the response, not model-authored claims.
    plan["meta"] = {
        "model": response.model,
        "prompt": prompt_path,
        "tools": [tool["name"] for tool in tool_schemas],
    }
    return plan


def revise_plan(client, plan: dict, step_results: list[dict], trace=None) -> dict:
    """Propose a repair from structured evidence and protect completed work."""
    prompt_path = "prompts/reviser.md"
    schema = json.loads((ROOT / "agent/plan_schema.json").read_text())
    # An allowlist excludes args, raw tool output, and any extra issue-text fields.
    safe_results = [{key: copy.deepcopy(result[key])
                     for key in ("id", "tool", "status", "count", "paths", "error_code")
                     if key in result} for result in step_results]
    current = copy.deepcopy(plan)
    statuses = {result["id"]: result.get("status") for result in safe_results}
    for step in current.get("steps", []):
        if step.get("status") == "done" or statuses.get(step["id"]) == "done":
            step["status"] = "done"
        elif step["id"] in statuses:
            step["status"] = statuses[step["id"]]
    # The caller retains original plan placeholders; filled arguments live only
    # in execution history and step_results, never in this plan.
    response = client.create(
        system=(ROOT / prompt_path).read_text(),
        messages=[{"role": "user", "content": json.dumps({
            "plan": {"steps": current.get("steps", [])},
            "allowed_tools": plan.get("meta", {}).get("tools", []),
            "step_results": safe_results,
        })}],
        tools=[{"name": "submit_plan", "description": "Return the repaired plan only.",
                "input_schema": schema, "strict": True}],
    )
    if trace is not None:
        trace.model_call(0, response, purpose="revise")
    calls = response.tool_calls
    if (len(calls) != 1 or calls[0].name != "submit_plan"
            or not isinstance(calls[0].input, dict)):
        revised = {}
    else:
        revised = copy.deepcopy(calls[0].input)
    proposed = revised.get("steps")
    if isinstance(proposed, list) and all(isinstance(step, dict) for step in proposed):
        completed = [(i, step) for i, step in enumerate(current.get("steps", []))
                     if step.get("status") == "done"]
        done_ids = [step["id"] for _, step in completed]
        proposed = [step for step in proposed if step.get("id") not in done_ids]
        for step in proposed:
            if "status" in step:
                step["status"] = "pending"
        # Restore completed steps and their positions even if the model omitted,
        # rewrote, or moved them. Remaining defects are for the caller to reject.
        for position, step in completed:
            proposed.insert(position, copy.deepcopy(step))
        revised["steps"] = proposed
    revised["meta"] = {"model": response.model, "prompt": prompt_path,
                       "tools": copy.deepcopy(plan.get("meta", {}).get("tools", []))}
    return revised
