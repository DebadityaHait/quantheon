# Flash-trio reasoning-effort curves — predeclared plan

**Date:** 2026-09-30 (declared BEFORE launch)
**Extends:** runs #143 / #144 (the flash-trio board, every contestant at `high`).
**Question:** How does each flash model's desk performance and cost change with
`reasoning_effort` — what is the *shape* of each curve, and do the three share it?

## Design

- **Models (fixed):** `gpt-6-luna` (`openai/gpt-6-luna`), `mimo-2-6-flash`
  (`xiaomi/mimo-v2.6-flash`), `deepseek-v4-1-flash` (`deepseek/deepseek-v4.1-flash`,
  pinned to DeepSeek's own upstream). All through the zenmux channel, exactly as in
  #143/#144.
- **Arms (7 new):**

  | model | new arms | re-used | curve points |
  |---|---|---|---|
  | gpt-6-luna | `low`, `medium`, `xhigh` | `high` | 4 |
  | mimo-v2.6-flash | `low`, `medium` | `high` | 3 (ladder ends at `high`) |
  | deepseek-v4.1-flash | `low`, `max` | `high` | 3 (native ladder) |

- **Workflows (6, all current):** `risk-limit-breach-day` v1, `ops-settlement-day` v1,
  `risk-manager-control-day` v1, `high-board-portfolio-review-day` v2,
  `trader-rfq-booking-day` v3, `confirmation-desk-day` v3 (designed par 9). The same
  manifest versions #143/#144 ran — checked at declaration time.
- **Trials:** 2 per (workflow, arm) → 84 new trials, folded per cell by
  `fold_trial_breakdowns`, the same trial count as the `high` point.
- **Jury:** off. Objective-only scoring, output budget unpinned (as #143/#144).
- **Execution order:** the loop is workflow → model → arm → trial, so all effort
  arms of one workflow run in the same time window; comparisons are paired by workflow.

## The re-used `high` point

`high` is NOT re-run. It is taken from #143 (five workflows) and #144
(trader-rfq v3), using the scored rows as they stand after the 65662ed
arg-matching rescore (mimo ops-settlement = row 679). Justification, checked at
declaration: since #144's base (70c5b8b) the only backend change is 65662ed, which
is scoring-only and already applied to those rows; all six manifest versions and
pars are unchanged. The residual confound is time (#143/#144 ran 2026-09-26/27);
it is stated, not hidden.

## Pre-launch knob probe (done 2026-09-30, before this plan)

`scripts/smoke_reasoning_efforts.py` proves **acceptance only**: its 17×23 prompt
gave 10–36 reasoning tokens at every level for all three models. A hard counting
prompt (7-digit integers, digit sum 30, no equal adjacent digits), N=4 per level,
measured whether each level actually **changes** reasoning spend (median reasoning
tokens):

| level | gpt-6-luna | deepseek via zenmux | deepseek direct (api.deepseek.com) |
|---|--:|--:|--:|
| none | — | thinking off | — |
| low | 952 | 43k | 39k |
| medium | 3.5k | 57k | 48k |
| high | 6.4k | 46k | 46k |
| xhigh | 15.0k | 54k | 48k |
| max | — | 60k | 47k |

mimo (easier prompt; `xhigh` rejected): low 869 · medium 1,023 · high 2,043.

- **luna and mimo have live, monotone knobs** — luna roughly doubles per step.
- **DeepSeek-V4.1-Flash's knob is weak, and not because of the gateway.** DeepSeek's
  own `/models` publishes `effort.supported_levels: [low, high, max]` (default
  `high`); its request parser accepts the OpenAI superset, so `medium`/`xhigh` are
  accepted aliases. Hence the native-ladder arms. Directly, even `max` did not
  separate from `high`; only `none` (thinking off) is a large contrast, and it is
  deliberately NOT in this study.

## Hypotheses (stated before data)

1. **luna repeats #110's shape** (gpt-5.6-luna): the gain is at `low`→`medium`, flat
   above, and `xhigh` costs calls and wall-clock for ≤ 1 point of objective.
2. **deepseek's curve is flat** within per-cell noise — predicted by the knob probe.
   A flat deepseek curve is therefore a statement about the knob, not about whether
   thinking helps deepseek.
3. **Effort's sign is task-shaped** (as in #110): procedural workflows saturate or
   decline; judgment-heavy (high-board) and solve-type (trader-rfq price tolerance)
   gain.
4. **Tool-call direction is model-specific**: luna's calls rise with effort; no
   prediction for mimo or deepseek.

## Predeclared metrics

1. **Primary:** objective score per (workflow, arm) cell; each model's curve is the
   mean over workflows, compared **paired by workflow** across arms.
2. **Secondary:** card axes (GRD/ADH/SYN/PRC/EFF/CON, OVR), tool calls per trial,
   per-cell trial spread, wall-clock per trial, tokens (reasoning / output / input /
   cache) and billed USD from `score_breakdown.usage`.
3. **Commensurable x-axis:** effort labels are vendor-specific (deepseek's `high` is
   not luna's `high`), so a second set of curves plots score against **measured
   reasoning tokens per trial**. Only that chart overlays the three models.
4. **Mechanism:** per-check pass-rate tally across arms, to locate where effort
   helps or hurts.

## Predeclared validity rules

- Trials that die from infra (`invalid`, infra-blank / infra-contaminated) are
  excluded; a cell with 0 clean trials is reported **missing, never imputed**.
- If more than ~20% of trials are infra-dead, stop and `--resume` into the same run
  rather than conclude from a swept board.
- Pinned-effort board: comparable to #143/#144 (also pinned) only; never to
  unpinned boards on EFF/CON.
- n = 6 workflow blocks × 2 trials per point. Report signs and means of paired
  differences; sub-point differences are not interpreted. Run #107 vs #108 showed a
  6.6-point swing at identical config — the noise floor is real.
- Billed cost requires `scripts/arena_cost_report.py --billed`, run by the user
  with their management key; list-price cost is reported until then.
