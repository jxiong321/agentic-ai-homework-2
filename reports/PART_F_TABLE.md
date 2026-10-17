# Part F measured results

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
