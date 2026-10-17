"""Part A only: one real planner request, no issue reads or comments.

Run from the repository root: python -m eval.probe_plan
The evidence is separate from measured Part F/G runs.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

from harness import ROOT
from harness.backends import make_backend
from harness.client import ModelClient
from harness.pricing import PriceSheet
from harness.settings import load_settings
from harness.trace import TraceWriter, read_trace
from tools import read_issue, search_repo, read_file, post_comment
from ways.planned import prepare_plan


def main():
    settings = load_settings()
    if not settings.api_key_env or not os.environ.get(settings.api_key_env):
        raise SystemExit(f"Set {settings.api_key_env or 'your API key variable'} in this terminal first.")
    client = ModelClient(make_backend(settings.provider, settings),
                         PriceSheet(ROOT / "pricing.yaml"),
                         session_ceiling=settings.session_token_ceiling)
    path = ROOT / "reports/part_a_probe.jsonl"
    trace = TraceWriter(path, "part-a-planner-probe", {
        "lab": "02", "way": "planned", "issue": 4191,
        "backend": settings.provider, "model": settings.model,
        "scope": "Part A planning-only development probe",
    })
    schemas = [m.SCHEMA for m in (read_issue, search_repo, read_file, post_comment)]
    try:
        prepare_plan(SimpleNamespace(client=client, issue_number=4191,
                            tools=SimpleNamespace(schemas=schemas), trace=trace))
    except Exception:
        trace.close()
        raise
    trace.run_end(client.totals(), error=None)
    records = read_trace(path)
    accepted = any(r["type"] == "model_call" and r.get("purpose") == "plan" for r in records)
    plans = [r for r in records if r["type"] == "plan"]
    assert not any(r["type"] == "tool_call" for r in records)
    print("Strict-marked planner request accepted:", accepted)
    print("Schema-valid plan logged:", bool(plans))
    if plans:
        for step in plans[-1]["plan"]["steps"]:
            print(f"  {step['id']}: {step['tool']} — {step['action']}")
    else:
        for r in records:
            if r["type"] == "schema": print("Schema errors:", r["errors"])
    print("No issue tools executed and no comments posted.")
    print("Evidence:", path)
    print("Usage:", client.totals())
    print("Acceptance does not prove provider enforcement of strict mode.")


if __name__ == "__main__":
    main()
