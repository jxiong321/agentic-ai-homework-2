"""Way 5, planned: RepoMind with a plan it cannot quietly abandon. This file is yours.

Assignment 2, Parts B, C and D. Like every way, run(ctx) -> None (see ways/__init__.py):

    python run.py --way planned --set dev
    python run.py --way planned --critique self --set dev      # or external; off is the default

The run, in order (checks/FORMATS.md, section 10):

  1. Plan: agent.plan.make_plan(ctx.client, ctx.issue_number, ctx.tools.schemas,
     trace=ctx.trace). The planner never sees the issue.
  2. Check, then validate. First the plan against agent/plan_schema.json, with
     harness.schema.errors (a vendor may accept "strict" and not enforce it), and
     that its last step is post_comment (a plan without one passes the four checks
     and posts nothing); a plan that breaks either writes
     ctx.trace.event("schema", errors=...). Then agent.validator.validate(plan). A
     plan that fails any of these is rejected and re-planned, at most MAX_REPLANS
     times; then the run escalates: ctx.trace.end("escalated", detail), no tool
     call, nothing posted.
  3. Log: ctx.trace.plan(1, plan), before the first tool call.
  4. Execute the steps in order, each tool call through ctx.call_tool, naming the
     plan step it runs for: ctx.call_tool(n, tool, args, plan_step=step["id"]). Where a step
     has arguments marked "$fill", one model call fills them in: offer it that
     step's tool alone, and trace it with ctx.trace.model_call(n,
     response, purpose="execute"). Act on the tool calls a response holds,
     whatever its stop_reason says. The executor may run, retry or halt a step; it
     may not add, drop or reorder one. A call that is not the current step's tool
     never runs: refuse it and write ctx.trace.event("off_plan", step=..., tool=...).
  5. Part C: revise only at one checkpoint, after a search step: the first search
     step, and any search step a revision added or changed, until MAX_REVISIONS is
     spent; and only when the check there fails (a check in code, not in a prompt,
     such as "the search returned at least one source file, not only documentation
     or translations"): revise_plan, which never changes a step that is done but may
     change a failed one to retry it, then check the new version against the schema
     and validate it, write
     ctx.trace.event("revision", checkpoint=..., version=..., valid=...), and log a
     valid one with ctx.trace.plan(version, plan). A revision that fails the
     validator never runs, and counts against the bound.
  6. Part D: before post_comment, the second pass, in the mode ctx.critique names
     (off, self or external), at most MAX_ROUNDS rounds. A round checks the
     current draft (agent.critique.verify, or agent.critique.self_critique) and
     writes ctx.trace.event("critique", round=..., mode=..., result="pass" or
     "fail", reason=..., changed=..., draft=...). A draft that fails, with a round
     left, is rewritten by one model call given the reason, traced with
     purpose="critique", and the next round checks the new draft. A draft still
     failing in the last round is held: not posted, and the run ends escalated.
     Nothing is posted until the last round, and a run posts one comment at most.

The comment is Assignment 1's: two lines, label: and file: (section 1). A run that
finishes its plan can leave its ending to the runner, which writes completed.

Part G's ways/notes.py extends this way without changing it, so build this one with
hooks it can override: for example an executor class whose methods run after every
step, build what each model call sees, and run before the comment.

The checker reads MAX_REPLANS, MAX_REVISIONS and MAX_ROUNDS from this module, and
runs this way against scripted models (harness/scripted.py). You can run them too,
free:

    python run.py --way planned --backend harness.scripted:AlwaysInvalidPlanner --set dev
    python run.py --way planned --backend harness.scripted:OffPlanExecutor --set dev
    python run.py --way planned --critique external --backend harness.scripted:DraftNamesUnseenFile --set dev
"""

from __future__ import annotations

import json
import time

from agent.loop import load_bounds
from agent.critique import verify, self_critique
from harness.formats import result_paths

from agent.plan import make_plan, revise_plan
from agent.validator import validate
from harness import ROOT
from harness.schema import errors

MAX_REPLANS = 2        # Two recovery attempts after the initial plan; at most three calls.
MAX_REVISIONS = 2      # Accepted and rejected repair attempts both consume this bound.
MAX_CANDIDATE_PATHS = 5
MAX_ROUNDS = 2         # Check, optionally rewrite once, then check again.


def plan_errors(plan: dict) -> list[str]:
    """Check structure and JSON argument encoding before semantic validation."""
    schema = json.loads((ROOT / "agent/plan_schema.json").read_text())
    problems = errors({k: v for k, v in plan.items() if k != "meta"}, schema)
    if problems:
        return problems
    steps = plan["steps"]
    for step in steps:
        try:
            args = json.loads(step["args_json"])
        except (ValueError, TypeError):
            problems.append(f"step {step['id']}: args_json must be valid JSON")
        else:
            if not isinstance(args, dict):
                problems.append(f"step {step['id']}: args_json must encode an object")
    if not steps or steps[-1]["tool"] != "post_comment":
        problems.append("the plan must end with post_comment")
    if any(step["tool"] == "post_comment" for step in steps[:-1]):
        problems.append("post_comment may appear only as the final step")
    ids = [step["id"] for step in steps]
    if len(set(ids)) != len(ids):
        problems.append("plan step ids must be unique")
    return problems


def prepare_plan(ctx) -> dict | None:
    """Return and log an approved plan, or end the run without tool execution."""
    for attempt in range(MAX_REPLANS + 1):
        plan = make_plan(ctx.client, ctx.issue_number, ctx.tools.schemas, trace=ctx.trace)
        problems = plan_errors(plan)
        if problems:
            ctx.trace.event("schema", errors=problems, attempt=attempt + 1)
            continue
        result = validate(plan)
        ctx.trace.event("validation", attempt=attempt + 1, **result)
        if not result["valid"]:
            continue
        ctx.trace.plan(1, plan)
        return plan
    ctx.trace.end("escalated", f"No valid plan after {MAX_REPLANS + 1} planner attempts.")
    return None


def has_fill(value):
    if isinstance(value, dict):
        return any(has_fill(v) for v in value.values())
    if isinstance(value, list):
        return any(has_fill(v) for v in value)
    return value == "$fill"


def preserves_fixed(template, actual):
    if template == "$fill":
        return True
    if isinstance(template, dict):
        return isinstance(actual, dict) and all(
            k in actual and preserves_fixed(v, actual[k]) for k, v in template.items())
    if isinstance(template, list):
        return isinstance(actual, list) and len(template) == len(actual) and all(
            preserves_fixed(a, b) for a, b in zip(template, actual))
    return type(template) is type(actual) and template == actual


class PlannedExecutor:
    """Execute approved steps in order; hooks allow later review and notes."""

    def __init__(self, ctx, plan):
        self.ctx = ctx
        self.plan = plan
        self.history = []
        self.step_results = []
        self.schemas = {s["name"]: s for s in ctx.tools.schemas}
        self.bounds = load_bounds()
        self.started = time.monotonic()
        self.version = 1
        self.revisions = 0
        first_search = next((step["id"] for step in plan["steps"]
                             if step["tool"] == "search_repo"), None)
        self.checkpoint_ids = {first_search} if first_search is not None else set()

    def messages_for(self, step):
        return [{"role": "user", "content":
                 f"Execute the current step for issue #{self.ctx.issue_number}.\n"
                 + json.dumps({"step": step, "history": self.history})}]

    def after_step(self, step, result):
        """Hook for checkpoint revision and durable notes in later parts."""

    def before_comment(self, step, args):
        """Review drafts before any post; both modes share the same bound."""
        mode = getattr(self.ctx, "critique", "off")
        if mode == "off":
            return args
        draft = args["body"]
        evidence = {"issue_number": self.ctx.issue_number, "history": self.history}
        for round_number in range(1, MAX_ROUNDS + 1):
            if mode == "external":
                verdict = verify(draft, self.ctx)
                passed = verdict["passed"]
                reason = "; ".join(verdict["reasons"]) if not passed else None
            elif mode == "self":
                verdict = self_critique(self.ctx.client, draft, evidence, trace=self.ctx.trace)
                passed = verdict["decision"] == "accept"
                reason = verdict["reason"]
            else:
                self.stop(f"Unknown critique mode: {mode}")
                return None
            next_draft = draft
            if not passed and round_number < MAX_ROUNDS:
                response = self.ctx.client.create(
                    system=(ROOT / "prompts/rewrite_comment.md").read_text(),
                    messages=[{"role": "user", "content": json.dumps({
                        "draft": draft, "reason": reason, "evidence": evidence})}],
                    tools=None,
                )
                self.ctx.trace.model_call(0, response, purpose="critique")
                next_draft = response.text.strip()
            self.ctx.trace.event("critique", round=round_number, mode=mode,
                                 result="pass" if passed else "fail", reason=reason,
                                 changed=next_draft != draft, draft=draft,
                                 revised_draft=next_draft if next_draft != draft else None)
            if passed:
                return {**args, "body": draft}
            draft = next_draft
        step["status"] = "failed"
        self.stop("Draft failed review at the two-round limit; no comment posted.")
        return None

    def stop(self, detail):
        self.ctx.trace.end("escalated", detail)

    def fill_arguments(self, number, step, template):
        response = self.ctx.client.create(
            system=(ROOT / "prompts/executor.md").read_text(),
            messages=self.messages_for(step), tools=[self.schemas[step["tool"]]])
        self.ctx.trace.model_call(number, response, purpose="execute")
        calls = response.tool_calls
        # Inspect the entire response before allowing any side effect.
        wrong = [c for c in calls if c.name != step["tool"]]
        for call in wrong:
            self.ctx.trace.event("off_plan", step=step["id"], tool=call.name,
                                 input=call.input, reason="tool differs from current step")
        if wrong or len(calls) != 1:
            self.stop("Executor must request exactly one call to the current step's tool.")
            return None
        args = calls[0].input
        if not preserves_fixed(template, args):
            self.ctx.trace.event("off_plan", step=step["id"], tool=calls[0].name,
                                 input=args, reason="changed a fixed argument")
            self.stop("Executor changed an argument fixed by the plan.")
            return None
        return args

    def revise_at_checkpoint(self, step):
        """Accept a validated repair here only; rejected proposals never execute."""
        while self.revisions < MAX_REVISIONS:
            self.revisions += 1
            candidate = revise_plan(self.ctx.client, self.plan, self.step_results,
                                    trace=self.ctx.trace)
            problems = plan_errors(candidate)
            verdict = validate(candidate) if not problems else {"valid": False, "failures": []}
            old_steps = {s["id"]: s for s in self.plan["steps"]}
            if not problems and verdict["valid"]:
                # A repair must leave a search to resolve this failed checkpoint.
                pending_searches = [s for s in candidate["steps"]
                                    if s["status"] != "done" and s["tool"] == "search_repo"]
                if not pending_searches:
                    problems.append("checkpoint repair must retain or add a pending search")
                # Completed work forms an immutable prefix in this sequential executor.
                done = [s for s in self.plan["steps"] if s["status"] == "done"]
                if candidate["steps"][:len(done)] != done:
                    problems.append("revision moved or changed completed work")
            valid = not problems and verdict["valid"]
            if problems:
                self.ctx.trace.event("schema", errors=problems, version=self.version + 1)
            self.ctx.trace.event("revision", checkpoint=step["id"], version=self.version + 1,
                                 valid=valid, attempt=self.revisions,
                                 failures=verdict["failures"])
            if not valid:
                continue
            for revised in candidate["steps"]:
                if revised["tool"] == "search_repo" and revised["status"] != "done":
                    previous = old_steps.get(revised["id"])
                    if previous is None or revised != previous:
                        self.checkpoint_ids.add(revised["id"])
            self.plan = candidate
            self.version += 1
            self.ctx.trace.plan(self.version, candidate)
            return True
        self.stop("Search checkpoint failed; two revision attempts exhausted.")
        return False

    def run(self):
        number = 0
        while True:
            step = next((s for s in self.plan["steps"] if s["status"] != "done"), None)
            if step is None:
                return
            number += 1
            if (number > self.bounds.max_steps
                    or self.ctx.client.total_tokens >= self.bounds.max_tokens
                    or time.monotonic() - self.started >= self.bounds.wall_clock_s):
                self.stop("Executor reached its step, token, or time bound.")
                return
            template = json.loads(step["args_json"])
            args = self.fill_arguments(number, step, template) if has_fill(template) else template
            if args is None:
                step["status"] = "failed"
                return
            problems = errors(args, self.schemas[step["tool"]]["input_schema"])
            # Bare tool schemas allow extra properties; Python tool functions do not.
            allowed = self.schemas[step["tool"]]["input_schema"].get("properties", {})
            if isinstance(args, dict):
                problems += [f"unexpected argument: {key}" for key in args if key not in allowed]
            if problems or has_fill(args):
                step["status"] = "failed"
                self.stop("Invalid tool arguments: " + str(problems or ["unresolved $fill"]))
                return
            if step["tool"] == "post_comment":
                args = self.before_comment(step, args)
                if args is None:
                    return
            result = self.ctx.call_tool(number, step["tool"], args, plan_step=step["id"])
            step["status"] = "failed" if result.is_error else "done"
            paths = result_paths(step["tool"], args, result.content, result.is_error)
            checkpoint_failed = (step["id"] in self.checkpoint_ids
                                 and step["tool"] == "search_repo"
                                 and not 1 <= len(set(paths)) <= MAX_CANDIDATE_PATHS)
            if checkpoint_failed:
                step["status"] = "failed"
            self.history.append({"id": step["id"], "tool": step["tool"], "args": args,
                                 "result": result.content, "status": step["status"]})
            self.step_results.append({"id": step["id"], "tool": step["tool"], "status": step["status"],
                                      "paths": paths, "count": (len(result.content.splitlines()) if paths else 0) if step["tool"] == "search_repo" else None,
                                      "error_code": ("tool_error" if result.is_error else
                                                     "no_matches" if checkpoint_failed and not paths else
                                                     "too_many_paths" if checkpoint_failed else None),
                                      "args": args})
            self.after_step(step, result)
            if checkpoint_failed:
                if not self.revise_at_checkpoint(step):
                    return
                continue
            if result.is_error:
                self.stop(f"Tool failed at step {step['id']}.")
                return


def run(ctx) -> None:
    plan = prepare_plan(ctx)
    if plan is not None:
        PlannedExecutor(ctx, plan).run()
