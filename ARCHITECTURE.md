# ARCHITECTURE.md · RepoMind on the seven layers

For each layer: what does this job, and where is it enforced. Cite code as a file
path and line number joined by a colon, inside backticks; a checker opens every
reference (`checks/FORMATS.md`, section 8). A layer held only by a sentence in a
prompt (any file under `prompts/`) is **EMPTY**, and so is a layer nothing does
yet. Status is one of: present, partial (say what is missing), or **EMPTY**. Each
assignment brings this file up to date.

What each layer is for (Lecture 1, slides 40 to 42):

- **Model**: reasoning, choosing tools, generating text.
- **Harness**: runs the loop, builds each prompt, trims old history.
- **Tools**: where the system acts on the world.
- **Memory & State**: what survives a step, a session, a restart.
- **Control & Policy**: what the system may do, and when it must ask.
- **Observability**: a step-by-step record of what it did.
- **Evaluation**: measuring quality, before and after release.

The table below includes Assignment 2's plan validation, execution boundary,
review, progress notes, and compaction.

| Layer | What does this job | Where it is enforced | Status |
|---|---|---|---|
| Model | The configured model, called only through the metered client | `harness/client.py:116` | present |
| Harness | The bounded loop; plan schema checks and validator before execution; executor boundary; checkpoint revision; notes-mode compaction | `agent/loop.py:38`, `agent/validator.py:34`, `ways/planned.py:110`, `ways/planned.py:223`, `ways/planned.py:238`, `ways/notes.py:78` | present |
| Tools | Four tools behind one registry (read_file arrived with Assignment 2's starter); post_comment stamps the run_id | `tools/__init__.py:52`, `harness/tracker.py:60` | present |
| Memory & State | Versioned plans in the trace and a per-run JSON progress file updated after each tool step in notes mode | `ways/planned.py:122`, `ways/planned.py:272`, `ways/notes.py:63`, `ways/notes.py:99` | partial: durable records, no automatic cross-run resume |
| Control & Policy | Rejects invalid plans, refuses off-plan calls, and holds drafts that fail bounded review; allows post_comment only as the final plan step | `ways/planned.py:102`, `ways/planned.py:124`, `ways/planned.py:173`, `ways/planned.py:223` | partial: enforced boundaries, no human approval gate |
| Observability | Model and tool traces, versioned plans, and logged validation, off-plan, revision, critique, compaction, and memory-question events | `ways/planned.py:119`, `ways/planned.py:122`, `ways/planned.py:202`, `ways/planned.py:225`, `ways/planned.py:260`, `ways/notes.py:91`, `ways/notes.py:139` | partial: traces, no alerts |
| Evaluation | Grounded triage scoring from the tracker; trace detectors and diff; generated comparison and context results | `eval/check_triage.py:7`, `agent/detectors.py:41`, `agent/diff.py:71`, `eval/summarize_lab02.py:25`, `eval/summarize_context.py:12` | partial: offline only |

**Empty layers: 0 of 7**; Memory & State, Control & Policy, Observability, and Evaluation remain partial. Durable notes do not implement automatic resume, and automated checks do not implement human approval.
