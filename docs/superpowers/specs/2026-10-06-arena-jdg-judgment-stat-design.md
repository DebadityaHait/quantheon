# Arena JDG — a judgment stat beside EFF (design)

Date: 2026-10-06 · Status: approved in brainstorming, awaiting spec review ·
Delivery: **phase 1** (this spec's implementation plan) + **phase 2** (separate plan, only
if the phase-1 validation passes).

## 1. Why

EFF scores fewer counted tool calls as better (golf curve against a per-workflow par,
gated by correctness). It was justified as an intelligence proxy: *a model that picks the
fitting tool by judgment needs fewer calls than one that enumerates.* Research on
2026-10-06 tested that premise and did not support it:

- **Call taxonomy** (runs #143/#144/#145, flash trio, 119 trials, 8,568 counted calls):
  deepseek-v4.1-flash's 45 extra calls/trial over gpt-6-luna were 37 % exploratory, and only
  ~7 % were genuine tool discovery. The rest: cross-step re-reads (fresh `task()` subagent per
  step), per-entity fan-out, verification, offload read-back, input-document reads.
- **Searches did not choose tools.** 8 % of DeepSeek's searches looked up a tool name and
  ~1 % led to a tool it then used for the first time; 92–99 % of its `/skills` greps came
  after it had already read a SKILL.md that step.
- **Thinking did not replace calls.** Calls rose with reasoning effort (deepseek 61 → 92 → 200,
  low → max) at a flat score.
- **Call count did not predict the score** (within model × workflow, p = 0.27), nor did four
  candidate process metrics — the flash-trio objective was saturated (arm means 90–96).
- **Ablation (run 146, research branch `arena-fs-ablation`, not merged):** DeepSeek with the
  filesystem removed and every skill inlined kept its correctness (Δ +0.7 after excluding
  checks unreachable by construction) and its call count (+7 %); the searching was
  **rerouted** into artifact/domain calls. Call count is a disposition, not a judgment signal.

So EFF honestly measures **cost**. What it was meant to measure — judgment — needs its own
stat, and that stat must be validated against an outcome that varies before it moves a
ranking.

## 2. Decisions (made by the user in brainstorming)

| # | Decision |
|---|---|
| D1 | Both inside OVR eventually: the EFF weight (0.16) splits into **EFF (cost) 0.08 + JDG 0.08**. |
| D2 | EFF (cost) keeps today's formula: golf curve on counted calls vs the provenance-frozen par, correctness-gated. Tokens / USD / wall time stay in the advisory usage readout. |
| D3 | JDG is built from four signals: same-step repeats, dead searches, first-call selection, calibration on trap steps. |
| D4 | Rollout: **validate, then promote.** Phase 1 = compute, persist, backfill, show advisory, run a predeclared validation. Phase 2 = OVR change behind a provenance-stamped card scheme, only on a pass. |
| D5 | Approach A: metrics derived from the **transcript** (not the trace DB), persisted at write time, backfilled from stored transcripts. |
| D6 | The existing advisory jury score `JDG` is renamed **SBJ** (subjective, peer of OBJ); the name **JDG** goes to the new stat. |
| D7 | A manifest step label `trap: true`, including the two candidate steps (§4). |
| D8 | The no-fs ablation switch never goes to `main`. |

## 3. The stat

Names: **JDG** (judgment, new) · **SBJ** (the jury score, renamed from JDG; values and rules
unchanged: advisory, outside OVR, outside the tie-break).

All signals use **counted calls only** (`trace_harvest.META_TOOLS` excluded, as for EFF) and
are scoped to **one step**. Cross-step re-reads are never charged: every `task()`
delegation is a fresh persona without memory, so they are architecture-forced.

Definitions used below:
- *domain call* — a counted call that is not `ls`/`grep`/`glob` (fs search), `run_python`,
  `record_answer`, or `write_todos`.
- *write call* — a tool whose `_RISK_LEVEL_BY_TOOL` level in `deep_agent/hitl.py` is
  `"write"` or `"irreversible"`. Authoritative; never inferred from the tool name.
- *read call* — a domain call that is not a write call.
- *step text match* — a transcript step is **matched** to the current manifest step with the
  same index only if its `user` text equals that manifest step's `user` text. Manifest-dependent
  signals (S, K) use matched steps only, so a label never applies to an older manifest era
  whose step differed. W is manifest-independent and uses every step.

### 3.1 W — waste (0..1)

A counted call (excluding `record_answer`) is **wasted** if either:

1. **same-step repeat** — an identical `(tool name, canonical args)` occurred earlier in the
   same step **with no write call between them** (a write can legitimately change what a
   re-read returns); canonical args = JSON with sorted keys;
2. **dead search** — an `ls`/`grep`/`glob` whose result is empty (empty string, `[]`, or a
   result starting `No matches found` / `No files found`), or a `grep` whose `pattern` string
   (case-insensitive, literal) already appears in an earlier counted tool result of the same
   step.

`waste_rate = wasted / (counted − record_answer calls)`;
`W = max(0, 1 − waste_rate / WASTE_ZERO)` with **`WASTE_ZERO = 0.30`** (predeclared; reference
points: deepseek@high ≈ 10 %, luna@high ≈ 3 %). No denominator → W undefined.

Known under-detection, accepted: uncounted `read_file` results (skill text) are not in the
transcript, so a grep for text that was only in a SKILL.md the agent read is not caught.

### 3.2 S — selection (0..1)

A step is **scored** when it is matched, its **accepted set** is non-empty, and it contains
at least one domain call. Accepted set = names in `expected_tools` ∪ every tool named by a
step-scoped assertion of a tool-naming type **other than `tool_not_called`** — today
`tool_called`, `tool_result_path`, `tools_routed_sequence`, `own_result_read`,
`response_quotes_tool_value`, `tool_result_ratio`, recursing into each branch of
`assertion_any_of`. A name that appears only in a `tool_not_called` assertion is never
accepted. The workflow's session-level `success` block is not step-scoped and is ignored.
The rule is by exclusion on purpose: a tool-naming assertion type added later is accepted
automatically, and a test enumerates the schema's types so a new NEGATIVE type cannot be
missed.

`S = hits / scored_steps`, where a hit = the step's first domain call is in its accepted set.
No scored step → S undefined.

### 3.3 K — calibration (0..1)

Per trial: `R = mean read calls per matched trap step / mean read calls per matched routine
step`. `K = clamp((R − 0.5) / 1.5, 0, 1)` (predeclared): R = 0.5 → 0, uniform effort R = 1 →
0.33, double effort on traps R = 2 → 1. K undefined when the trial has no matched trap step,
no matched routine step, or zero routine reads.

### 3.4 Composition

`JDG = round(99 × C × mean(defined sub-scores among W, S, K))`, where `C` is the same
correctness gate EFF uses (`scoring._correctness`: GRD + ADH + SYN pass rate). All three
undefined → JDG is `None` (uncarded, shown as "—", never 0).

**Phase 1:** JDG is a **top-level** card key (`card["jdg"]`), beside `sbj` and `con` — not in
`card["stats"]`, and so outside `_OVR_WEIGHTS`, `_CARD_TIEBREAK_PRIORITY` and `_card_position`.
(Amended during planning: the leaderboard averages every key in `stats` and the exporters
enumerate fixed stat lists, so a possibly-`None` advisory value must not live there. Phase 2
moves it into `stats` when it enters OVR.) OVR, tie-break and position labels of every board
are byte-identical to today.

## 4. The `trap` label

**Definition:** `trap: true` marks a step whose naive completion is wrong — the competent
move is to refuse, abstain, or detect an absence/defect. A design property written by the
manifest author, never inferred from results.

**Schema:** `Step.trap: bool = False` in `golden_workflows/schema.py`.

**Labels (0-indexed steps):**

| workflow | step | naive-wrong action | evidence |
|---|---|---|---|
| high-board-portfolio-review-day | 5 | certify the inline figure as the official governed valuation | manifest prose |
| ops-settlement-day | 1 | book a payment for a put that expired worthless | manifest prose |
| ops-settlement-day | 7 | reopen the knocked-out snowball | manifest prose |
| risk-manager-control-day | 7 | stress with the non-existent `stagflation-shock-2011` set | manifest prose |
| trader-rfq-booking-day | 9 | build an unsupported `cliquet-ratchet` product | manifest prose |
| risk-limit-breach-day | 4 | waive the incident (graded answer: `hold_for_verification`) | check verified 2026-10-06 |
| confirmation-desk-day | 6 | invent conf-07's missing initial price (graded: `null` + `invalid`) | check verified 2026-10-06 |

Every workflow has ≥ 1 trap step, so K is defined on all six. Each labelled workflow bumps
`manifest_version` (the label is scoring-relevant through JDG); the sha256 changes, so
`--resume` refuses runs stamped before the bump and `merge_runs` refuses to fold across it —
intended. No objective check changes, so objective scores are unaffected.

## 5. Persistence, card, backfill

### 5.1 `backend/app/services/arena/process_metrics.py` (new, pure)

`process_record(steps: list[dict], workflow) -> dict` — `steps` is the transcript's `steps`
list. Returns raw evidence, never scores:

```json
{"scheme": "jdg-v1", "manifest_version": 2,
 "waste":       {"repeats": 4, "dead_searches": 3, "denominator": 85},
 "selection":   {"scored_steps": 6, "hits": 2},
 "calibration": {"trap_steps": [5], "trap_reads": 9, "trap_n": 1,
                 "routine_reads": 41, "routine_n": 6},
 "matched_steps": 8, "unmatched_steps": 0}
```

`trap_steps` records the indices used, so a later relabel cannot silently move a stored JDG
(freeze-at-write, like par). Sub-scores and JDG are computed **on read** in `scoring.py` from
these counts, so constants are versioned by `scheme`, not baked into rows.

### 5.2 Write time — `arena/task.py`

Where each trial's breakdown gets `diagnosis` and `usage`, also attach
`breakdown["process"] = process_record(transcript["steps"], loaded.workflow)`. A failure
inside `process_record` is logged and stored as `{"unavailable": "<reason>"}`; it never fails
a match.

### 5.3 Card — `arena/scoring.py`, `arena/store.py`

- `card_from_axes(..., process: dict | None = None)` adds `card["jdg"]` (or `None`). The
  return dict's `"jdg"` key is renamed **`"sbj"`** (jury value, unchanged); the trial fold
  (`aggregate_card_from_trials`) folds `sbj` as it folded `jdg`, and folds JDG as the mean of
  non-`None` trial JDGs.
- `store._derive_card` passes `bd.get("process")` through. It remains the single
  stored-breakdown → card path, so board and drilldown cannot disagree.
- New pure helpers in `scoring.py`: `waste_score`, `selection_score`, `calibration_score`,
  `jdg_stat` — each takes the raw record, returns 0..1 or `None`.

### 5.4 API and frontend

- Every arena route that carries a card: the card keeps `stats` as a free dict; `sbj`
  replaces `jdg`. Routes with a pydantic `response_model` or a hand-built key projection
  (`routers/arena.py`, see its existing comments) are updated; **an HTTP-layer test asserts
  `card.jdg` and `sbj` survive both kinds of route.**
- `frontend/src/lib/arenaApi.ts`: `jdg` → `sbj`; the card gains `jdg: number | null`.
- `Arena.live.tsx` drilldown card: a JDG chip labelled "advisory", rendered like SBJ; the
  radar and leaderboard OVR column are unchanged in phase 1.

### 5.5 Backfill — `scripts/backfill_process_metrics.py`

`--run N` / `--all`, `--dry-run` (default) / `--write`.
- For each scored match and each trial, load the transcript (`transcript.trialN.json` or
  `transcript.json` next to `transcript_path`), compute `process_record`, and write it into
  the trial's breakdown (`aggregate[i].process`, plus the top level for a single-trial match).
- Adds one key; never modifies an existing one. The dry run derives every card before and
  after and **asserts OVR, the five OVR stats, CON and the tie-break key are identical**;
  `--write` refuses to run if the dry run would change any of them.
- Missing transcript → `process: {"unavailable": "transcript_missing"}`.
- Merged runs: processed only where their source trials' transcripts resolve; otherwise
  `unavailable`. (Validation excludes merged runs regardless — §6.)
- Uses the arena DB only; does not need the trace DB.

## 6. Phase-1 validation (predeclared — written before any JDG is computed)

Script: `scripts/arena_jdg_validation/` (extract → analyze → report), reproducible from the
arena DB + transcripts.

**Sample:** scored, **non-merged** matches (`config.merged_from` is null) with a process
record; infra-contaminated trials excluded (`task._is_infra_contaminated`); the high-board
9103 leak era (runs 115–140) flagged and reported with and without.

**Predictor:** **J₀** = mean of the defined W, S, K — the **ungated** core, because JDG's C
gate contains correctness and would make the test circular. Each sub-score is also tested
alone.

**Outcome:** trap-step correctness = pass rate of the checks on matched trap steps.

**Held out:** within each multi-trial match, the predictor from trial *i* is paired with the
outcome from a different trial *j* (all ordered pairs, i ≠ j). A trial never predicts itself.
Current inventory: 307 multi-trial non-merged matches, 33 models, 56 runs.

**Tests** (Spearman, mean within-workflow, stratified permutation, 10,000 draws):

| | test | pass |
|---|---|---|
| T1 | ρ(J₀ of trial i, trap correctness of trial j) | ρ > 0 and p < 0.05 |
| T1b | the same pairs with cost = calls / par as the predictor | ρ(J₀) > ρ(cost) |
| T2 | trial-to-trial reliability ρ(J₀ trial i, J₀ trial j) | ρ ≥ 0.5 |
| T3 | discriminant: \|ρ(J₀, calls / par)\| on the same trials | < 0.7 |

**Promotion rule:** JDG enters OVR (phase 2) only if J₀ passes T1, T1b, T2 and T3. Each
sub-score that fails T1 or T2 on its own is dropped from JDG at promotion (scheme
`jdg-v2`). If J₀ fails, JDG stays advisory and the negative result is published.

**Stated limitations:** observational data; model, effort and harness era are confounded;
within-workflow strata reduce but do not remove that. Constants (`WASTE_ZERO`, the K scaling)
are fixed by this spec and are not tuned on the validation data.

## 7. Phase 2 (separate plan, only on a pass)

- `arena_run.provenance.card_scheme`: `"v1"` (today) or `"v2"`. Derive-on-read honours the
  stamp; **absent = v1**, so no published board's OVR or rank moves. Runs stamp v2 only after
  the promotion commit.
- v2 weights: GRD .32, ADH .26, SYN .16, **EFF .08, JDG .08**, PRC .10. Tie-break
  GRD → ADH → SYN → JDG → EFF → PRC. `_card_position` gains JDG → **"Strategist"**. Radar
  gains a seventh axis (JDG); SBJ stays off the radar. CON unchanged.
- A v2 match without a process record is uncarded (fail-honest), never JDG = 0.
- `merge_runs` refuses mixed schemes; the leaderboard exporter refuses to rank v1 with v2.
- Re-carding an old board is explicit only: `rescore_arena_match.py --card-scheme v2`, new rows,
  old stamps kept.
- EFF keeps its key and formula, displayed as "EFF (cost)".
- Docs at promotion: artena methodology page (SBJ rename note, v2 definitions, the
  validation result), README, CHANGELOG, `golden_workflows/CLAUDE.md` card section.

## 8. Testing (phase 1)

- `tests/test_process_metrics.py` — hand-built transcripts:
  - identical reads with a write between → not waste; without → waste;
  - dead search: empty result; `No matches found`; grep whose pattern is in an earlier result;
  - selection: `any_of` branch accepted; a name only in a `tool_not_called` assertion not
    accepted; every schema assertion type is classified tool-naming-positive / negative /
    not-tool-naming (the test fails on an unclassified new type);
    first call fs/`run_python` skipped; step with no domain call not scored;
  - calibration: no trap step → K undefined; unmatched step text → excluded;
  - `trap_steps` recorded.
- `tests/test_arena_scoring.py` — sub-score formulas and edge values; JDG `None` when all
  undefined; **OVR unchanged** with and without a process record; `sbj` folds as `jdg` did.
- `tests/test_arena_api.py` / `test_arena_store.py` — HTTP layer carries `card.jdg` and `sbj`.
- Backfill dry run on a fixture DB: cards byte-identical, one key added.
- `golden_workflows` tests — `Step.trap` parses; the seven labels load; manifest versions
  bumped (enumerate exact-set pins first: `grep -rln "manifest_version" tests/`).
- Frontend: `Arena.live.test.tsx` — `jdg` → `sbj` fixtures; the advisory JDG chip renders;
  `npx tsc --noEmit`.

## 9. Risks

- **Selection re-grading the route.** Mitigated by the accepted set including every positive
  assertion branch; validated by T1/T2 before it can affect a rank.
- **Stale step-text matching** excludes historical steps from S and K when manifests changed;
  `matched_steps`/`unmatched_steps` are recorded so coverage is visible.
- **Manifest bumps** make in-flight resumes impossible; launch nothing between the bump and a
  new run.
- **The rename** touches two published posts' prose ("JDG (jury) … was not run"); they are
  dated and stay as published; the methodology page records the rename.
