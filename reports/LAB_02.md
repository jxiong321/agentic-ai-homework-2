# Assignment 2 report · A plan RepoMind cannot quietly abandon

Every number here that has a field in `reports/LAB_02.json` goes there too: the
checker reads that file (format: `checks/FORMATS.md`, section 10.10). Give each
number its run count. Mark any vendor figure you cite with its source and the date
you read it.

## Part A · The plan artifact

I chose to use args_json instead of using separate argument shapes. The reasoning for this is twofold: first, filling in argument types can get complicated, especially if in the future, we don't know if we should allow an eventual integer or temporary "$fill" string. Second, it's complex: we need a branch for each tool to separately define the argument types. Args_json is simpler but we do need to check for errors later: in the later tasks we write code to reject malformed plans and check the tool, but this is still better because when the executor checks the arguments against the tool's schema, we do it at execution time and don't have to make duplicate schemas.

The schema has 0 optional fields out of the assignment's budget of 24 and 2 union-typed fields out of 16 (`tool` and `expected_result` are required but nullable); both objects forbid extra properties, with 8 total properties and a maximum depth of 5 under the checker's counting convention. On 2026-10-15, Gemini accepted one request carrying this schema with `strict: true` and returned a schema-valid plan, so `strict_compiles` is true under the assignment's acceptance criterion.

Evidence: `reports/part_a_probe.jsonl`, generated with `.venv/bin/python -m eval.probe_plan`: one live planner call, 922 prompt tokens, 327 output tokens, and $0.001094 according to the harness price sheet. Version 1 includes the model, prompt path, and tool names; no issue tools ran and no comment was posted. This is a Part A development probe, not a measured evaluation run.

## Part B · The validator and the boundary

| Plan | Valid | Failures (step, check) |
|---|---|---|
| `good_export_fix.json` | Yes | None |
| `good_triage.json` | Yes | None |
| `s18_specimen.json` | No | step 2, check 2, step 3, check 3, step 5, check 1 |

I set MAX_REPLANS =2 because I wanted to allow the plan more than one retry, because it may introduce new issues, so a second try gives another opportunity to produce a valid plan. Escalation costs human labor as it records a failure that needs to be inspected, so it's important to strike a balance between escalating too much , and too little.

Out of the initial planning, including re-plan attempts, 3 broke the schema or did not end with post_comment, out of 57 generated plans. And for revision attempts, this occurred 4/39 times.

I chose for each argument-filling call to see the current step and all earlier tool results, including the issue, previous arguments, and returned content. I chose this so the executor can use all the evidence gathered so far and see what it has already tried, rather than risk leaving out useful information by showing only dependency specific results. The tradeoff is higher token use and potentially distracting context as the run grows.

## Part C · Revision at a checkpoint
The checkpoint fails when a search returns zero or more than five distinct file paths.

`MAX_REVISIONS = 2` (accepted and rejected attempts combined).

## Part D · A second pass before posting

1. Format: the draft starts with label: (a known label) and file: (a path or none).
2. Existence: a named path must be a file inside the repository.
3. Evidence: this run must have seen the path in a successful search or read.
4. Consistency: question requires none; all other labels require a file.

`MAX_ROUNDS = 2`: check, allow one rewrite, then check again; a final failure is held.

Mode 1: Off. A check cannot find the error because we don't have a second pass. Therefore, there's no critic, so it can't know more. And a limit and log don't apply.

Mode 2: Self. A check can find an error (Gemini might notice a mistake), but it's not guaranteed. The critic (Gemini) does NOT know more, since it gets the same issue and gathered evidence used to produce the original draft. There is a limit and log: at most two rounds, each logged.

Mode 3: External. It catches the errors that we specifically check for. The critic may know more because the review now adds direct repository and trace checks, but it doesn't get new understanding of the bug. And there is a limit of at most two rounds and a log.

## Part E · Detectors and the diff

Calls match by plan_step when present, with matching tool and fixed arguments; otherwise each call consumes the earliest unmatched compatible plan step. `$fill` is a wildcard, and unspecified arguments do not constrain matching. Calls with no matching step are extra; an executed step is reordered if its plan position is earlier than the highest position already matched. The expected-result check flags missing calls or tool errors, not whether returned content proves task success.

| Diagnostic question | Looping run | Export-bug run (s49) |
|---|---|---|
| 1. Repeated actions? | Yes, turns 1 and 3 repeat the search, and turns 2 and 4 repeat the read. | Yes: turns 2/4 |
| 2. Unused results? | Judgment: turns 3 and 4 repeat the same actions and recorded results, with no demonstrated new contribution | No orphan plan steps under the recorded dependencies |
| 3. Every planned step executed? | No: plan steps 3, 4, 5, and 6 lack matching successful calls | No: plan step 6, confirm the button works, was skipped |

The looping run has neither dependency declarations nor detailed returned paths, so question 2 is a redundancy judgment based on identical calls and result summaries, not proof that the results were unused; the summary also cannot establish where the later exportButton search term came from.

Question 4, looping: This plan addresses the right task but is too vague to guide or verify progress. “Identify the bug” gives no observable completion criterion. “Fix the bug” doesn’t specify what the fix depends on, and “verify the fix works” doesn’t name a test or expected behavior.

Question 4, export-bug: the plan matches the task by reproducing, locating, patching, retesting, and confirming the export behavior, but the run reports success while the test still fails and confirmation never ran.

Export-bug diff: steps 1–5 executed; step 6 skipped; trace turn 4 extra.

## Part F · What the plan and the second pass bought
Three sweeps a configuration: a pilot, not a settled difference.

| Measure | Agent | Planned, off | Planned, self | Planned, external |
|---|---|---|---|---|
| Passes, of 18 | 15 | 4 | 4 | 5 |
| Per issue, 4201–4206, each of 3 | 3, 3, 3, 3, 3, 0 | 2, 1, 0, 0, 1, 0 | 3, 0, 0, 0, 1, 0 | 3, 1, 0, 0, 1, 0 |
| Sweep passes: lowest–highest, of 6 | 5–5 | 1–2 | 1–2 | 1–2 |
| Mean tokens per run | 12,882.4 | 5,933.7 | 7,751.6 | 6,919.1 |
| Latency seconds: median / slowest | 6.57 / 12.34 | 6.88 / 9.10 | 6.93 / 11.07 | 5.66 / 11.17 |
| Plan + revision prompt share, mean |  | 36.3% | 29.3% | 29.7% |
| Review prompt share, mean |  |  | 26.0% | 10.1% |
| Runs with an exact repeat | 1 | 0 | 1 | 0 |
| Off-plan attempts |  | 2 | 1 | 1 |
| Revisions per run: mean / maximum |  | 0.67 / 2 | 0.72 / 2 | 0.78 / 2 |
| Review rounds per run: mean / maximum |  |  | 1.11 / 2 | 1.33 / 2 |
| Drafts changed / fixed / broken |  |  | 4 / 0 / 0 | 6 / 0 / 0 |
| Drafts held |  |  | 3 | 5 |
| Total cost, USD (harness prices) | $0.0730 | $0.0579 | $0.0704 | $0.0640 |

Plan-call-only prompt share, grouped by number of model calls:

| Configuration | Model calls per run | Runs | Mean plan-only share |
|---|---|---|---|
| planned_off | 2 | 1 | 62.2% |
| planned_off | 4 | 7 | 26.4% |
| planned_off | 5 | 1 | 42.4% |
| planned_off | 6 | 7 | 14.9% |
| planned_off | 7 | 1 | 22.7% |
| planned_off | 8 | 1 | 10.8% |
| planned_self | 2 | 1 | 63.5% |
| planned_self | 4 | 1 | 24.4% |
| planned_self | 5 | 5 | 21.0% |
| planned_self | 7 | 7 | 14.8% |
| planned_self | 8 | 1 | 6.8% |
| planned_self | 9 | 3 | 9.1% |
| planned_external | 4 | 5 | 24.9% |
| planned_external | 5 | 5 | 20.8% |
| planned_external | 6 | 2 | 13.7% |
| planned_external | 7 | 2 | 12.4% |
| planned_external | 8 | 4 | 9.6% |

Generated by `eval/summarize_lab02.py` with `.venv/bin/python -m eval.summarize_lab02`. Per-run evidence: `reports/part_f_runs.csv`; grouped overhead: `reports/part_f_plan_overhead.csv`.

1. **What did the plan buy RepoMind, concretely?** Artifacts and counts, not
   qualities.

   The plan gave RepoMind a recorded sequence of intended actions and code that could check and constrain execution. Across all 54 planned runs, every run had an initial plan logged before tool execution. The system rejected 3 of 57 initial planning attempts for schema problems, refused and logged 4 off-plan attempts, and accepted 35 of 39 revision attempts. Including those accepted revisions, it saved 89 plan versions. Tool calls carried plan-step IDs, allowing us to compare what was planned with what actually ran.

   However, these controls did not improve triage accuracy in this pilot. The original agent produced 15/18 correct triages, compared with 4/18 for planned-off, 4/18 for planned-self, and 5/18 for planned-external. The concrete benefit was therefore a record we could inspect and boundaries we could enforce, rather than better answers in these runs.

2. **Where did it not pay?** Slide 52's four cases, applied to your six issues. On
   which would the plan cost more than the execution?

   None of the six issues was a one-step task in our implementation: each required reading the issue, gathering repository evidence, and posting a comment. However, the broad sequence was predictable across all six, so a fixed workflow could potentially replace the generated plan. We did not test that alternative here. The case where nobody reads the plan also does not apply, because our validator, executor, and plan-versus-trace comparison use it.

   Using prompt tokens as the cost measure, planning plus revision did not exceed execution on average for any issue. It did exceed execution in 8 of the 54 individual planned runs: one on 4201, two on 4202, none on 4203, one on 4204, one on 4205, and three on 4206. All eight escalated before completion: four stopped after attempts to change fixed arguments, and four exhausted the revision limit. In those runs, planning consumed more prompt tokens than the execution performed, without producing a successful triage.

3. **What did each second pass buy, and what did it cost?** Which errors each mode
   caught, whether either turned a passing draft into a failing one, what each
   added in tokens and time, what happened to issue 4206 under each, and which of
   slide 41's three gates each mode passes.

   With review off, RepoMind performed no second-pass checks and produced 4/18 correct triages. Self-review also produced 4/18: it noticed problems such as unverified file paths and blaming a translation file rather than the implementation, but it added no new evidence. It changed drafts in 4 runs and held 3 drafts without posting. External review produced 5/18 correct triages and caught format errors, missing or unseen paths, and inconsistencies between the label and file. It changed drafts in 6 runs and held 5. Neither review mode turned a failing draft into a passing outcome or a passing draft into a failing outcome under the assignment’s scoring.

   The additional review and rewrite calls averaged about 1,990 tokens and 1.32 seconds per run for self-review, compared with 610 tokens and 0.36 seconds for external review. These averages include runs that stopped before reaching review. Review calls accounted for an average of 26.0% of prompt tokens in self mode and 10.1% in external mode; external checks themselves required no model call.

   Issue 4206 failed in all three modes: each configuration posted two incorrect comments naming src/export/csv.ts and escalated once before posting. Self-review accepted that diagnosis. External review also accepted it because the file existed, the run had seen it, and the comment passed the format and consistency checks. Those checks could not establish that the file was actually responsible for the bug.

   For the lecture’s three gates, off mode has no critic or review loop. Self-review can notice errors but knows no more than the original drafter; it has a two-round limit and a log. External review can detect the specific violations we check for and uses direct repository and trace verification, but gains no independent diagnosis of the bug; it also has a two-round limit and a log.

4. **Which failure did no detector catch?** Did you see a run that reported success
   before the task was done, and how did you know?

   The detectors missed an incorrect diagnosis after the plan had been fully executed. For example, run planned-4206-s01-808f26 posted “label: bug” and “file: src/export/csv.ts,” passed external review, and ended as completed. The repeat, orphan, and expected-result checks raised no flags, and the diff marked all four planned steps executed with no extra calls. However, the independent evaluator marked the answer wrong because the expected file was src/ingest/dedupe.ts.

   This shows the limit of detecting premature stopping from execution records alone: every planned action can finish while the actual task remains unsuccessful. The model did not explicitly announce success in this run. It posted its final answer, and the runner recorded “completed.” The outside correctness check exposed the failure that the internal checks missed.

## Part G · Note-taking against compaction

<!-- BEGIN GENERATED CONTEXT TABLE -->

| Issue | Notes | Sweep | Correct / 6 | Compactions | Estimated notes tokens | Total tokens |
|---|---|---|---|---|---|---|
| 4203 | off | 1 | 6 | 4 | 0 | 7182 |
| 4203 | off | 2 | 6 | 4 | 0 | 7063 |
| 4203 | on | 1 | 5 | 4 | 194 | 7320 |
| 4203 | on | 2 | 6 | 4 | 194 | 7432 |
| 4204 | off | 1 | 6 | 4 | 0 | 6837 |
| 4204 | off | 2 | 6 | 4 | 0 | 9082 |
| 4204 | on | 1 | 6 | 1 | 80 | 2635 |
| 4204 | on | 2 | 6 | 4 | 332 | 12022 |
| 4206 | off | 1 | 3 | 2 | 0 | 10564 |
| 4206 | off | 2 | 3 | 2 | 0 | 10644 |
| 4206 | on | 1 | 3 | 3 | 496 | 11823 |
| 4206 | on | 2 | 6 | 1 | 80 | 2723 |

Notes tokens are character-based estimates for the progress-file text included in executor and question requests, not an exact vendor token attribution. Total tokens come from provider usage.

Generated with `.venv/bin/python -m eval.summarize_context`; per-run evidence is in `reports/part_g_runs.csv`, and all six answers and trace-based truth labels are in `reports/LAB_02.json`.

<!-- END GENERATED CONTEXT TABLE -->

`COMPACT_AT = 600`. The progress file holds a record of executed steps and encountered paths.

1. **What did the progress file keep that compaction lost,** and what did the file
   cost in tokens?

   The progress file preserved the explicit record of executed steps and encountered paths outside the conversation. On issue 4206, searches returned CHANGELOG.md, README.md, and docs/API.md, but later summaries omitted those exact paths. Both notes-off runs incorrectly answered that they had not seen them. The progress file retained those paths, although the comparable notes-on run still answered incorrectly, showing that retaining information does not guarantee the model will use it.

   Overall, notes-off scored 30/36 and notes-on scored 32/36. This is not clear evidence that notes recovered two lost memories, because the runs followed different trajectories: two notes-on runs ended before seeing any files and correctly answered no to all six questions. One notes-on run also denied seeing src/i18n/en.json even though both its summary and progress file contained that path, so not every memory error was caused by compaction.

   Showing the progress file added approximately 1,376 estimated prompt tokens across six notes-on runs, or about 229 per run. These are character-based estimates of the file text included in requests, not exact provider-measured token costs.

2. **Which context operations did RepoMind need?** Structured note-taking,
   sub-agent isolation, just-in-time retrieval and compaction, in that order: for
   each, whether your longest run in Part F needed it, and what it would have cost.

   I used agent-4206-s03-0e5a5c as the longest run: it tied for the most model calls at 12 and had the highest cumulative token usage, 22,736 tokens. Its largest individual prompt was only 3,276 tokens; cumulative usage is not the same as context size. It ended at the turn limit, not a context limit.

   Structured note-taking could preserve completed steps and encountered paths, but this run does not demonstrate that it needed a separate progress file. The costs would be writing updates, maintaining accurate state, and adding tokens when the notes are shown to the model. Our Part G results also showed that available notes were not always used correctly.

   Sub-agent isolation was not clearly needed for this small, sequential investigation. A separate investigation could have its own context, but would add model calls and coordination, while potentially losing details in the summary returned to the main agent.

   Just-in-time retrieval was useful and already present: the run searched for relevant code and then read src/export/csv.ts and src/exportUtils.ts when it needed their contents. This avoided loading the whole repository upfront, at the cost of tool calls and tokens for the retrieved content.

   Compaction was not shown to be necessary for this run. Its individual prompts were modest, and it stopped because of the turn limit. Compaction would add summarization calls and risk losing details, as our Part G experiment demonstrated. The 600-token threshold in Part G was a deliberately low test setting, not evidence that ordinary RepoMind runs require compaction.

## Assistance
I used OpenAI Codex to help write and debug the code, generate results tables, and run automated checks. For the written answers, AI helped me understand what the questions were asking, break down the concepts, interpret my results and their implications, and brainstorm and draft some responses. I reviewed the code and explanations, ran the live experiments, and checked and revised the written answers to reflect my understanding.

[View the AI assistance conversation](https://chatgpt.com/s/cx_6ad2fc92905481919844bb32061a6bce).
