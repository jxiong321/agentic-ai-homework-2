"""Assignment 2, Part D: the second pass before posting. This file is yours.

Two ways to read a drafted comment before it is posted (Lecture 2, slides 31 to 34).
The checker runs your planned way in each mode against scripted models, so keep
these exact signatures (checks/FORMATS.md, section 10.2). You may add keyword
arguments with defaults; the checker passes only these.

    verify(draft, ctx) -> {"passed": bool, "reasons": [str, ...]}

        The external mode: checks in code, against the repository and this run's
        own record. Four checks:
          1. the draft parses: a `label:` line with a known label, and a `file:`
             line with a path or none (section 1; harness.formats.parse_triage_comment);
          2. a path it names exists in the repository (ctx.root / "fixtures" / "repo");
          3. this run saw that path: a search_repo result or a read_file call in this
             run's trace returned it. Each tool_call line's `paths` field lists the
             files it returned; read the trace so far with
             harness.trace.read_trace(ctx.trace.path);
          4. the label and the file agree: a question names none, and every other
             label names a file.
        "reasons" says why each failed check failed; it is empty when all pass.
        verify reads only what the run itself can see: never the answer key, and
        never Assignment 1's grounded check in eval/. The checker flags a second
        pass that does.

    self_critique(client, draft, evidence, trace=None) -> {"decision": "accept" | "revise", "reason": str | None}

        The self mode: one model call that rereads the draft, given the issue and
        what the run's steps returned (`evidence`, a dict of your design), and
        accepts it or asks for a revision with a reason. Given a trace, trace the
        call: trace.model_call(n, response, purpose="critique").

    draft   the comment your executor drafted, the text post_comment would post
    ctx     the run's harness.runner.WayContext
    client  harness.client.ModelClient

The loop that uses them, its rewrite call and MAX_ROUNDS live in ways/planned.py.
Keep your prompts in prompts/.
"""

from __future__ import annotations

import json

from harness import ROOT
from harness.formats import LABELS, parse_triage_comment, normalize_path
from harness.trace import read_trace


def verify(draft: str, ctx) -> dict:
    reasons = []
    lines = draft.strip().splitlines() if isinstance(draft, str) else []
    label, path = parse_triage_comment(draft if isinstance(draft, str) else "")
    if (len(lines) < 2 or not lines[0].lower().startswith("label:")
            or not lines[1].lower().startswith("file:")
            or label not in LABELS or path is None):
        reasons.append("format: start with label: <bug|feature|question|docs> and file: <path|none>")
    if path is not None and path != "none":
        root = (ctx.root / "fixtures" / "repo").resolve()
        target = (root / path).resolve()
        if root not in target.parents or not target.is_file():
            reasons.append("existence: named path is not a file in the repository")
        seen = {normalize_path(p) for row in read_trace(ctx.trace.path)
                if row.get("run_id") == ctx.run_id and row.get("type") == "tool_call"
                and row.get("name") in ("search_repo", "read_file") and not row.get("is_error")
                for p in row.get("paths", [])}
        if path not in seen:
            reasons.append("evidence: this run has not seen the named path in a search or read")
    if label in LABELS and path is not None:
        if (label == "question") != (path == "none"):
            reasons.append("consistency: question requires none; every other label requires a file")
    return {"passed": not reasons, "reasons": reasons}


def self_critique(client, draft: str, evidence: dict, trace=None) -> dict:
    schema = {
        "type": "object",
        "properties": {"decision": {"type": "string", "enum": ["accept", "revise"]},
                       "reason": {"type": ["string", "null"]}},
        "required": ["decision", "reason"], "additionalProperties": False,
    }
    response = client.create(
        system=(ROOT / "prompts/self_critique.md").read_text(),
        messages=[{"role": "user", "content": json.dumps({"draft": draft, "evidence": evidence})}],
        tools=[{"name": "review_draft", "description": "Accept the draft or request a revision.",
                "input_schema": schema, "strict": True}],
    )
    if trace is not None:
        trace.model_call(0, response, purpose="critique")
    calls = response.tool_calls
    if len(calls) == 1 and calls[0].name == "review_draft":
        verdict = calls[0].input
        if verdict.get("decision") == "accept":
            return {"decision": "accept", "reason": None}
        if verdict.get("decision") == "revise":
            return {"decision": "revise", "reason": str(verdict.get("reason") or "Reviewer requested revision.")}
    return {"decision": "revise", "reason": "Reviewer did not return a valid structured verdict."}
