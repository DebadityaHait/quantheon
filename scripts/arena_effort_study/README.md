# Reasoning-effort study (Run #145 post)

Reproduces `docs/arena/2026-10-02-run145-effort-curves.md`. Reads the live arena DB
(gitignored `data/`), so it runs only on a machine that holds it.

```bash
.venv/bin/python scripts/arena_effort_study/extract.py  /tmp/effort_trials.json   # trial-level dataset
.venv/bin/python scripts/arena_effort_study/analyze.py  /tmp/effort_trials.json /tmp/effort_report.json
.venv/bin/python scripts/arena_effort_study/power.py                               # detectable effect sizes
.venv/bin/python scripts/arena_effort_study/figures.py  /tmp/effort_trials.json /tmp/effort_figs.json
```

- **Studies:** `flash-trio` = #145 + the `high` point from #143 (five workflows) and
  #144 (trader-rfq v3); `luna56` = #110; `gemini38` = #134 (xhigh) / #138 (low).
- **Task-dependence tests** (`analyze.py`): an effort × workflow interaction by
  Freedman-Lane permutation of the additive model's residuals, and a cross-validated
  policy test (pick effort on one trial, score on the other; per-task vs one global
  effort, ties to the cheaper effort), with a null from the same permutations.
- **Figures** (`figures.py`): inline SVG small multiples in the site's `mid` hue,
  `<title>` hover, collision-checked labels. No JS — the blog's rule.
