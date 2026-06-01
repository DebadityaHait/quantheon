# JDG phase-1 validation — the judgment stat fails, in the wrong direction

2026-10-06 · protocol: `docs/superpowers/specs/2026-10-06-arena-jdg-judgment-stat-design.md` §6 ·
code: `scripts/arena_jdg_validation/` · verdict: **not promoted; JDG stays advisory**.

## What was tested

EFF charges every counted tool call. The 2026-10-06 call-taxonomy study and the no-fs
ablation (run 146, research branch `arena-fs-ablation`) showed call count measures an
evidence-gathering disposition, not tool-selection judgment. JDG was designed as the judgment
signal instead: per trial, from the trial's own transcript,

- **W, waste** — same-step repeats with no write between, and dead searches;
- **S, selection** — the share of steps whose first domain call the step accepts;
- **K, calibration** — read effort on `trap: true` steps relative to routine steps.

The test uses the **ungated** core J₀ = mean(W, S, K) (JDG's correctness gate would make it
circular) against **trap-step correctness** — the share of checks passed on the trial's trap
steps — always pairing the predictor from one trial with the outcome from a **different**
trial of the same match. The constants and the pass bars were written into the spec before
any JDG was computed.

## Sample

635 trial rows with a `jdg-v1` record (scored, non-merged matches; 40 models, 90 runs), 442
matches, of which 193 have ≥ 2 recorded trials. 376 held-out (i ≠ j) pairs carry both a
predictor and a trap outcome. The snapshot was taken after the add-only backfill; it is
identical to the live arena DB (662 matches, max id 725). Missing evidence is explicit, never
guessed: 161 non-merged trials have no transcript the backfill could map (48 rows store no
path; 89 belong to old runs that kept only the last trial's transcript), and merged runs are
excluded by design.

## Result

Mean within-workflow Spearman ρ; T1 p is one-sided for ρ > 0 (10,000 stratified permutations).

| predictor | T1 ρ (held-out trap correctness) | T1 p | T2 trial-to-trial ρ | T3 ρ with calls/par |
|---|--:|--:|--:|--:|
| **J₀** | **−0.174** | 0.999 | 0.171 | −0.239 |
| W | −0.066 | 0.878 | 0.479 | −0.544 |
| S | −0.097 | 0.958 | 0.363 | −0.182 |
| K | −0.161 | 0.996 | 0.163 | +0.086 |
| cost = −calls/par (T1b reference) | −0.146 | — | — | — |

Cost is oriented like EFF (fewer calls = higher), i.e. −calls/par; J₀ fails T1b under either
sign (−0.174 < ±0.146). Excluding the high-board 9103 leaked-view era (runs 115–140; 338 pairs):
J₀ ρ −0.221, W −0.064, S −0.155, K −0.184 — the same picture.

**Scheme note.** These are `jdg-v1.1` numbers. The first run used `jdg-v1`, whose waste count
double-counted a call that was both a repeat and a dead search and repeat-checked
`record_answer` while excluding it from the denominator (~7 % of the waste numerator), found
in the branch's final review. Correcting it moved J₀ T1 from −0.176 to −0.174 and W T2 from
0.400 to 0.479; the verdict did not change.

Against the predeclared rule (T1: ρ > 0 and p < 0.05; T1b: beats cost; T2: ρ ≥ 0.5; T3:
|ρ| < 0.7) **every predictor fails T1 and T2**; J₀ passes only T3. Promotion is refused.

## The finding is the sign

J₀ does not merely fail to predict trap correctness — it runs **against** it: the held-out
trial-pair association is negative. A descriptive model-level view (`analyze.py`'s
`model_level`, not a predeclared test; 15 models with ≥ 8 trap-scored trials, one row per
trial) points the same way, ρ −0.18; gemini-3.8-flash has the lowest J₀ (0.48) and the highest
trap correctness (0.97). The cost reference agrees: more calls per par go with *better* trap
behaviour (ρ of −calls/par is −0.146).

**Hypothesis, not a finding of cause.** Read together with the ablation, one consistent
reading is that the "efficient" process signatures — fewer repeats, a first call that hits the
expected tool, flat effort — mark **confidence**, which is what a trap step is built to catch:
a trap asks the model to stop and check, and models that check more pass it more often. These
are observational data, so this is a hypothesis for a controlled test, not an established
mechanism.

## Limits

Observational: model, effort and harness era are confounded; within-workflow strata reduce
that but do not remove it. Most matches have two trials, which makes the T2 reliability
estimate noisy (it does not cap it). Trap labels cover one or two steps per workflow, so the
outcome is coarse. The stratified permutation treats every held-out pair as exchangeable
although each trial appears in n − 1 pairs, so its p-values are anti-conservative — this can
only manufacture a false PASS, never the FAIL reported here. Trials whose manifest step text has since
changed fall out of S and K by design.

## What it means for the card

- JDG stays an **advisory** chip; OVR keeps EFF at 0.16 (phase 2 is not taken).
- EFF should be read — and labelled — as **cost**, not judgment.
- If a judgment signal is wanted, the evidence points at the outcome side (trap checks
  themselves, e.g. a TRP stat from trap-step pass rates) rather than at any process count.
