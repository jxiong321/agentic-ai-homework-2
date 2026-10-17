# CHANGES.md

Three lines per assignment: what it added, what it removed, what it constrained.
Removals are logged like additions.

## Assignment 1
- **Added:** a bounded tool loop; four ways to triage an issue (a direct call, a workflow, an agent, and a hybrid of the two); a grounded success check that reads the tracker; a results script
- **Removed:** nothing
- **Constrained:** every agent run to three bounds checked in code (steps, tokens, wall clock); success to what the tracker holds for the run's ID

## Assignment 2
- **Added:** a structured plan artifact and provenance log; a four-check validator and bounded reject exit; a search revision checkpoint; a second pass in off, self, and external modes; three detectors and a plan-versus-trace diff; a progress file and history compaction; scripts and reports for the 72 comparison runs and 12 context experiments.
- **Removed:** nothing.
- **Constrained:** the executor to the active validated plan, with off-plan calls refused and logged; revision to failed search checkpoints, preserving completed work; the comment to at most one post after the final successful review round when review is enabled, with failing drafts held at the bound.
