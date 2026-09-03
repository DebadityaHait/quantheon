# JDG phase-1 validation

Reproduces the predeclared test in
`docs/superpowers/specs/2026-10-06-arena-jdg-judgment-stat-design.md` §6. The constants
(`WASTE_ZERO = 0.30`, K = clamp((R − 0.5) / 1.5)) are fixed by the spec and must not be
tuned on this data.

```bash
PYTHONPATH=backend .venv/bin/python scripts/arena_jdg_validation/extract.py --db <arena sqlite> --out trials.json
PYTHONPATH=backend .venv/bin/python scripts/arena_jdg_validation/analyze.py --trials trials.json --out report.json
```

**Sample.** Scored, non-merged matches (`config.merged_from` is null) whose trials carry a
`jdg-v1` process record (written at match time, or added by
`scripts/backfill_process_metrics.py`). Infra-contaminated trials need no filter here:
`task._is_infra_contaminated` / `_is_infra_blank` return `invalid` before a trial is scored,
so they never enter a scored aggregate. High-board runs 115–140 (the 9103 leaked-view era) are
flagged `leak_era` and the analysis runs with and without them.

**Predictor.** J₀ = mean of the defined W, S, K — the UNGATED core (JDG's correctness gate
would make the test circular). W, S and K are also tested alone.

**Outcome.** Trap-step correctness: the pass rate of the checks on the trial's matched
`trap: true` steps.

**Held out.** Within each multi-trial match, the predictor from trial *i* is paired with the
outcome from a different trial *j* (every ordered pair i ≠ j). A trial never predicts itself.

**Tests** (mean within-workflow Spearman; stratified permutation, 10,000 draws):

| | test | pass |
|---|---|---|
| T1 | ρ(J₀ of trial i, trap correctness of trial j) | ρ > 0 and one-sided p < 0.05 |
| T1b | same pairs with cost (−calls/par) as the predictor | ρ(J₀) > ρ(cost), strictly |
| T2 | trial-to-trial reliability ρ(J₀ trial i, J₀ trial j) | ρ ≥ 0.5 |
| T3 | discriminant \|ρ(J₀, calls/par)\| | < 0.7 |

**Promotion rule.** JDG enters OVR (phase 2) only if J₀ passes T1, T1b, T2 and T3. A
sub-score failing T1 or T2 alone is dropped from JDG at promotion. A fail keeps JDG advisory
and is reported as a negative result.

**Limitations.** Observational data: model, effort and harness era are confounded; the
within-workflow strata reduce that but do not remove it.
