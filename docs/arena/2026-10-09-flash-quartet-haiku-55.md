# 🏆 OTC Desk Agent Arena — Claude Haiku 5.5 joins the flash tier

**Claude Haiku 5.5 takes the top consolidated card among four flash models, by 1.2
points over mimo-v2.6-flash. That is a tie: one workflow was run twice for every model, and
on the first pair of trials Haiku is second, 0.1 behind. Haiku has the best efficiency and
the lowest objective score, and it costs more than luna and mimo and about the same as
deepseek.**

*2026-10-09 · regrouped from runs `#143`, `#146`, `#147`, `#149` and `#150` (and `#148`, shown beside them) · 4 models × 6 workflows ×
2 trials · every contestant pinned to `high` reasoning effort · output budget unpinned ·
objective-only scoring (jury off) · **48 of 48 trials scored, zero invalid** · cost is
the gateway's per-call **bill** for the trio and for Haiku's risk-manager-control cell,
and a rate-verified estimate for Haiku's other five*

---

## The field

| Model | Lab | Route |
|---|---|---|
| **claude-haiku-5.5** | Anthropic | `anthropic/claude-haiku-5.5`, pinned to Anthropic's own upstream, Anthropic wire format |
| **gpt-6-luna** | OpenAI | `openai/gpt-6-luna` |
| **mimo-v2.6-flash** | Xiaomi | `xiaomi/mimo-v2.6-flash` |
| **deepseek-v4.1-flash** | DeepSeek | `deepseek/deepseek-v4.1-flash`, pinned to DeepSeek's own upstream |

The three non-Anthropic models are the [Runs #143 / #144 flash trio](2026-09-27-run143-flash-trio.md).
Haiku 5.5 was onboarded on 2026-10-08. Two things were checked before it ran, not assumed.
It can read an image-only scan: three of three reads of the scanned confirmation returned
the underlying, the strike and the full reference number correctly, and the confirmation
workflow refuses to launch for a model that does not declare it. And the gateway accepts all
seven reasoning-effort levels for it but reports no reasoning tokens, so "accepted" does
not prove the levels differ. This board therefore covers one level, `high`, for every
contestant.

---

## How this board was assembled

This is a **regroup**, not a merge. Each cell below is read from one declared run, and
every other run is ignored for that cell.

| Source | Cells | Why |
|---|---|---|
| `#143` | the trio, on four workflows | the published trio rows |
| `#146` | Haiku, on the same four | Haiku's own six-workflow run |
| `#147` | **all four models**, on high-board and trader-rfq | both were repaired on 2026-10-08, so everyone was re-run together |
| `#148` | **all four models**, on risk-manager-control | the first pair of trials on the repaired workflow (below); **not used in any cell**, shown beside the second pair |
| `#149` | Haiku, on risk-manager-control | the second pair of trials, on the same manifest; Haiku's cell |
| `#150` | the trio, on risk-manager-control | the second pair of trials, on the same manifest; the trio's cells |

The three workflows that stay on the earlier runs are risk-limit-breach, ops-settlement and
confirmation-desk.

Haiku's #146 rows for high-board (81.4) and trader-rfq (68.5) are **not used**: they ran on
the pre-repair manifests. The trio's #143/#144 rows for those two workflows are likewise
superseded.

The three reused workflows are scoring-identical to when the trio ran them.

- **risk-limit-breach, ops-settlement, confirmation-desk**: the only manifest change since
  #143 is an advisory `trap: true` label on one step each, which no score reads. The
  manifest version rose (v1→v2, v3→v4) and so did the hash; the checks did not change.
- **risk-manager-control** is not reused. Its stored "stale" risk run pinned position ids
  1–3, which on the live DB are not the control book's positions, so the trio (on v1) and
  Haiku (on v2, the label only) had both run on the same defective fixture. v3 seeds the
  real ids. All four models were re-run on it together (#148), and the earlier
  risk-manager-control rows (Haiku 92.3, luna 97.4, mimo 93.6, deepseek 97.4) are **not
  used**.
- **risk-manager-control was run twice for every model, and the board uses the second pair.**
  Haiku's first pair (#148) scored 89.7 and 79.5 (84.6). At the maintainer's request Haiku
  was re-run alone (#149: 92.3 and 94.9, 93.6) and the re-run replaced those two trials.
  Replacing only Haiku's would have given it a second chance the others did not get, so
  the trio were re-run too (#150) and their first pairs (#148) are replaced the same way.
  All three runs are on the same manifest (v3, hash `301e00e0`). Both pairs are shown
  below, and the headline is given both ways.

Different app builds were in play: #143 ran on `ccfdb292f` (some of its rows were re-run on
later builds before publication), #146 on `f30fe37e3`, #147 on `843a7b4c7`, #148 on `bbf84616d`, #149 on `6a306a894` and #150 on `fadd3aa98` (the last two are main at a docs-only distance from #148). A compaction defect that dropped part of the history after a summary was
fixed between #143 and #146. The only #143 match that compacted at all was a row that was
since superseded, so the reused `high` rows are not affected by it. #148 also ran with the generation-id
fix, and so did #149 and #150, so every one of their calls, Haiku's included, can be billed individually.

---

## Headline

Consolidated card: the mean of each model's six workflow cards.

| Model | OVR | GRD | ADH | SYN | PRC | EFF | CON | Objective | Tool calls / match |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **claude-haiku-5.5** | **87.5** | 94 | 96 | 99 | 93 | 59 | 86 | 94.8 | 34 |
| **mimo-v2.6-flash** | **86.3** | 94 | 95 | 99 | 96 | 49 | 88 | 95.9 | 57 |
| **gpt-6-luna** | **84.3** | 93 | 95 | 94 | 96 | 45 | 86 | 95.7 | 40 |
| **deepseek-v4.1-flash** | **81.5** | 96 | 96 | 97 | 95 | 14 | 88 | 96.5 | 76 |

- **The top two are close.** Haiku's 87.5 leads mimo's 86.3 by 1.2, inside two-trial
  noise, and luna (84.3) is not far behind. Haiku has the best efficiency (59, against 49
  for mimo and 45 for luna), and mimo is ahead on precision (96 against 93),
  consistency (88 against 86) and objective score. On the first pair of risk-manager-control trials the order of these two is
  reversed (table below).
- **deepseek-v4.1-flash is last on the card and first on the work.** It has the best
  objective score (96.3) and grounding, and an efficiency of 13: 74 tool calls a match,
  more than twice Haiku's 34. As on the earlier board, that gap is all of its distance from the top.
- **Haiku has the lowest objective score of the four (94.8)**, 1.1 below mimo and 1.7
  below deepseek. Its card is up there because it gets to the answer in fewer calls.

risk-manager-control was run twice for every model. The headline above uses the second
pair for all four; the first pair gives a different top two.

| Model | OVR, second pair (#149 / #150) | OVR, first pair (#148) | OVR, without the workflow |
|---|:--:|:--:|:--:|
| claude-haiku-5.5 | **87.5** | 86.2 | 88.2 |
| mimo-v2.6-flash | 86.3 | 86.3 | 87.0 |
| gpt-6-luna | 84.3 | 84.3 | 85.2 |
| deepseek-v4.1-flash | 81.5 | 81.0 | 81.2 |

Before the fix Haiku led by 0.3 (86.0 against 85.7). Haiku is first by 1.2 on the second
pair and second by 0.1 on the first, and leads on the five workflows that did not move
(88.2). So the honest reading is a tie between Haiku and mimo; the second pair is used for
the headline because every model has one, and the first pair is shown for the same reason.

---

## Workflow by workflow

Objective score, with the two trials in brackets, then CON.

| Workflow | source | claude-haiku-5.5 | gpt-6-luna | mimo-v2.6-flash | deepseek-v4.1-flash |
|---|---|:--:|:--:|:--:|:--:|
| risk-limit-breach | #143 + #146 | 97.3 (94.7 / 100) · 92 | 97.4 (97.4 / 97.4) · 86 | **100.0** (100 / 100) · 99 | **100.0** (100 / 100) · 99 |
| ops-settlement | #143 + #146 | 94.3 (97.7 / 90.9) · 79 | **95.5** (90.9 / 100) · 73 | 88.6 (88.6 / 88.6) · 82 | 90.9 (88.6 / 93.2) · 86 |
| risk-manager-control | #149 + #150 | 93.6 (92.3 / 94.9) · 79 | 97.4 (97.4 / 97.4) · 99 | **100.0** (100 / 100) · 82 | 97.4 (97.4 / 97.4) · 92 |
| high-board | #147 | 95.7 (100 / 91.4) · 73 | 92.8 (100 / 85.7) · 59 | **97.1** (97.1 / 97.1) · 92 | **97.1** (97.1 / 97.1) · 96 |
| trader-rfq | #147 | 91.1 (90.3 / 91.9) · 96 | 94.3 (93.5 / 95.2) · 99 | 92.8 (88.7 / 96.8) · 79 | **95.2** (93.5 / 96.8) · 69 |
| confirmation-desk | #143 + #146 | 97.0 (97 / 97) · 99 | 97.0 (97 / 97) · 99 | 97.0 (97 / 97) · 92 | **98.5** (97 / 100) · 89 |

Workflow cards, OVR · EFF:

| Workflow | claude-haiku-5.5 | gpt-6-luna | mimo-v2.6-flash | deepseek-v4.1-flash |
|---|:--:|:--:|:--:|:--:|
| risk-limit-breach | 94 · 85 | 85 · 49 | 99 · 99 | 83 · 0 |
| ops-settlement | 89 · 80 | 89 · 82 | 83 · 65 | 75 · 0 |
| risk-manager-control | 84 · 31 | 80 · 0 | 83 · 14 | 83 · 8 |
| high-board | 91 · 95 | 86 · 93 | 94 · 89 | 86 · 40 |
| trader-rfq | 80 · 15 | 83 · 27 | 78 · 14 | 81 · 31 |
| confirmation-desk | 87 · 47 | 83 · 20 | 81 · 11 | 81 · 6 |

Correctness is close to saturated again: the best and worst objective means are 1.5 points
apart, and the whole spread is Haiku trailing. Haiku has the best card on three workflows
(ops-settlement, tied with luna, confirmation-desk, and risk-manager-control), though it
trails the other three on risk-manager-control's objective score, by 3.8 to 6.4 points.

### The repaired risk-manager-control

Every model ran it twice, two trials each at `high`: #148 (all four), then #149 (Haiku)
and #150 (the trio). No call was truncated in any run; mimo had two malformed tool calls
in one #148 trial.

| Model, run | Objective | Trial 1 (checks) | Trial 2 (checks) | Misses |
|---|:--:|:--:|:--:|---|
| gpt-6-luna, #150 (used) | 97.4 | 38 / 39 | 38 / 39 | the stale-result wording check on step 1, both trials |
| gpt-6-luna, #148 | 97.4 | 38 / 39 | 38 / 39 | the same wording check, both trials |
| mimo-v2.6-flash, #150 (used) | **100.0** | 39 / 39 | 39 / 39 | none |
| mimo-v2.6-flash, #148 | 97.4 | 38 / 39 | 38 / 39 | `get_latest_risk_run` not called on step 3 (trial 1); the `read-risk-result` skill not routed on step 1 (trial 2) |
| deepseek-v4.1-flash, #150 (used) | 97.4 | 38 / 39 | 38 / 39 | the `read-risk-result` skill not routed on step 1, both trials |
| deepseek-v4.1-flash, #148 | 96.2 | 37 / 39 | 38 / 39 | the `read-risk-result` skill not routed on step 1, both trials (it routed `monitor-limits` in trial 1); the stale-result wording check (trial 1) |
| claude-haiku-5.5, #149 (used) | 93.6 | 36 / 39 | 37 / 39 | `read-risk-result` not routed in both trials; `run-risk` not routed in both (once it routed `product-term-interpretation`); `get_latest_risk_run` not re-called on step 3 (trial 1) |
| claude-haiku-5.5, #148 | 84.6 | 35 / 39 | 31 / 39 | below |

Each trio model scored the same or higher on its second pair (luna 97.4 and 97.4, mimo
97.4 and 100, deepseek 96.2 and 97.4), so the trio's re-run did not lower anyone. Haiku
rose by 9 points. On the second pair Haiku is last on this workflow by 3.8 points.

Haiku's #148 (first pair) misses, by trial:

- **Trial 1 (89.7, 35 of 39).** It never routed the `read-risk-result` skill on step 1
  and did not re-call `get_latest_risk_run` on step 3, answering from the run it had just
  seen (it said it "did not re-query the stored run"; the answer it recorded was
  correct). On step 5 it ran its Greeks landscape over -10% to +10%, then, asked for delta
  at -20%, recorded `null` rather than run a wider grid, because "the request did not ask
  for" one. That is the one check that cost real content. On step 9 it wrote the governance
  report without the string "AAPL" anywhere in it.
- **Trial 2 (79.5, 31 of 39).** It did not route the `read-risk-result` or `run-risk`
  skills (it called the pricing tools directly), and on step 7 it never called
  `run_backtest`. It reported the backtest as not run, saying the run needed the async
  track and it had no async dispatch tool, and handed the brief to a persona that only
  estimated it. That one step cost four checks. On step 9 it routed `create-risk-report`
  where the workflow expects `generate-report`.

The other three models' misses are single checks. Haiku's #148 misses were about not doing
steps: declining to widen a grid, and declining to start a backtest. **Neither recurred in
#149.** Both trials ran the -30% to +30% landscape and answered delta at -20% correctly,
and both called `run_backtest`. What did recur is skill routing: Haiku missed
`read-risk-result` in all four trials and `run-risk` in three of four. So the stable
weakness is the skill step; the two content failures were each one trial in four.

---

## Efficiency

Counted tool calls per match, mean of two trials, against each workflow's par.

| Workflow | par | claude-haiku-5.5 | gpt-6-luna | mimo-v2.6-flash | deepseek-v4.1-flash |
|---|:--:|:--:|:--:|:--:|:--:|
| risk-limit-breach | 25 | 28 | 37 | 22 | 70 |
| ops-settlement | 30 | 34 | 34 | 38 | 72 |
| risk-manager-control | 24 | 40 | 50 | 51 | 78 |
| high-board | 24 | 18 | 17 | 24 | 38 |
| trader-rfq | 35 | 64 | 60 | 64 | 59 |
| confirmation-desk | 9 | 18 | 44 | 141 | 137 |

Haiku is the leanest model on the confirmation desk by a wide margin: 18 calls for a morning
of PDFs and scans, against 44 for luna and about 140 for mimo and deepseek. It stays at or
near par on three more workflows. Its two inefficient workflows are
risk-manager-control (40 calls against a par of 24, an EFF of 31; the others make 50 to 78) and trader-rfq (64
against 35), where all four models overshoot.

---

## What it costs

Two stated bases, because the board spans two price lists. **Today's rates** puts all four
models on one price list (2026-10-09), so the columns compare like with like. **Billed, as
run** is what the gateway charged for the calls that were made, which for the trio mixes
the earlier and the later price of one model (below).

| Workflow | claude-haiku-5.5 | gpt-6-luna | mimo-v2.6-flash | deepseek-v4.1-flash |
|---|:--:|:--:|:--:|:--:|
| risk-limit-breach | $0.109 | $0.069 | $0.062 | $0.156 |
| ops-settlement | $0.115 | $0.063 | $0.092 | $0.140 |
| risk-manager-control | $0.438 | $0.142 | $0.175 | $0.206 |
| high-board | $0.102 | $0.065 | $0.076 | $0.101 |
| trader-rfq | $0.263 | $0.156 | $0.217 | $0.172 |
| confirmation-desk | $0.119 | $0.074 | $0.250 | $0.288 |
| **Twelve matches** | **$1.14** | **$0.57** | **$0.87** | **$1.06** |

What the gateway actually billed, against the same cells at today's rates:

| Model | Billed, as run | Today's rates | Calls billed | Basis |
|---|:--:|:--:|:--:|---|
| claude-haiku-5.5 | $0.44 on one workflow | $1.14 | 138 | per-call bill on risk-manager-control (#149); estimate on the other five |
| gpt-6-luna | $0.57 | $0.57 | 869 of 869 | per-call bill |
| mimo-v2.6-flash | $0.87 | $0.87 | 1075 of 1078 | per-call bill |
| deepseek-v4.1-flash | $0.98 | $1.06 | 1070 of 1070 | per-call bill |

- **Haiku is not the cheap one.** At today's rates it costs about 2.0 times luna, 31%
  more than mimo, and about 8% more than deepseek. Its list rate is low ($0.10 in, $0.50
  out per million tokens), but it makes about 190 model calls over the two trader-rfq
  trials and carries a large prompt each time.
- **luna and mimo are billed exactly as the list says.** The gateway's per-call bill sums
  to the same figure to the cent. (Three of mimo's 1,078 calls could not be looked up.)
- **deepseek's price doubled between the two sets of runs, and the bill shows it.** Its
  route lists two input prices; the gateway charged the lower one on every call of those runs. That
  lower price is twice what it was when #143 ran (table below). The two risk-manager-control
  runs are the exception (next paragraph).

| Workflow | Run | Billed | List, low end | Ratio |
|---|:--:|:--:|:--:|:--:|
| risk-limit-breach | #143 | $0.0782 | $0.1564 | 0.50 |
| ops-settlement | #143 | $0.0698 | $0.1395 | 0.50 |
| risk-manager-control | #150 | $0.4112 | $0.2056 | 2.00 |
| high-board | #147 | $0.1007 | $0.1007 | 1.00 |
| trader-rfq | #147 | $0.1725 | $0.1725 | 1.00 |
| confirmation-desk | #143 | $0.1438 | $0.2877 | 0.50 |

The four earlier cells cost half of today's low price or exactly that price. **The
risk-manager-control runs do not.** In #150, the cell used here, the gateway billed $0.411,
exactly twice the low end: every one of the 163 calls was billed at the **higher** listed
price. In #148 the first 140 of 162 calls were billed at the higher price and the last 22
at the lower one. So deepseek's price moved during #148 and stayed high in #150, and the
"low end" this board uses for like-for-like cost is the lower of two prices the gateway has
charged, not a fixed rate. Had every call been billed at the higher price, deepseek's
twelve matches would cost about $2.12 instead of $1.06 (risk-manager-control alone is $0.41
against $0.21). Its real bill for this board was $0.98. The cause of the switch is not
known from the data.

- **Haiku's figure is mostly an estimate, and the estimate was checked.** Five of its six
  workflows ran before the gateway's request id was stored. #148 and #149 stored it. #149's 138
  calls (the cell used) were billed one by one: **$0.437630 billed against $0.437630
  estimated**, the same to the sixth decimal, as #148's Haiku cell was ($0.337177 against
  $0.337177). That is a check on the method, on one workflow, not proof for the
  other five. The gateway's
  billing breakdown for a live Haiku call gives the real rates: $0.10 prompt, $0.50
  completion, $0.01 cache read and **$0.125 cache write** (5-minute), which the price list
  omits. Those, applied to the recorded token counts, give $1.14. Two assumptions are
  inside that: the 5-minute write rate, since the arena sets no cache lifetime (the
  1-hour rate would add about $0.20), and a 0.625 write rate for the 7 of 1,014 calls
  whose prompts passed the list's 100k-token step, inferred from the same 1.25× premium and
  worth about a cent.

---

## Haiku's profile

### It tells you when it will not act

On the operations day, the last step asks the agent to reopen a snowball whose knock-out
was recorded that morning, while the settlement it generated is still pending. The
correct move is to try, be refused by the desk, and report that nothing was recorded.

Haiku attempted the reopen, was refused, and reported that it was not recorded, in
**both** trials, and it never voided the pending settlement. luna did so in one of two
trials. mimo never refused, and cancelled the knock-out and voided the 512,500 CNY
settlement both times. deepseek declined without attempting the call in one trial and
reopened in the other.

### It overrides a desk adjustment

Haiku's ops-settlement losses are judgment calls on a row, not tool errors. Cashflow 9302 was stale
because the upstream print had been corrected after ops had manually adjusted the amount to
91,000. The workflow scores keeping the desk's number. In both trials Haiku adopted the
re-derived 90,000 and replaced the manual figure, reasoning that the override was
superseded. In one trial it also declined to release a payment, citing a missing
counterparty on the row, where the workflow expects the release. Both are defensible
readings of the row, and both cost points.

### It stopped at an error the others worked around

On the first Haiku run (#146), trader-rfq scored 68.5. The booking tool rejected a term
that the product builder had accepted. mimo and deepseek, which hit the same error in
run 143, retried without the term and booked. Haiku did not: in one trial it made no booking call, and in the other
it tried once and reported that nothing had been booked. After the booking tool was
repaired, Haiku scored 91.1 on #147. Its remaining losses there are scattered: it skipped
the submit-for-approval step in one trial, and missed an answer and an unsupported-family
check in the other. On the repaired workflow it is the lowest of the four, by 1.7 to 4.1
points, on two trials.

---

## What changed since the earlier board

- **The booking tool now accepts the term that the builder accepts.** `book_position`
  rejected `initial_price` for a barrier option whenever the terms used `exercise_date`.
  Fixed on 2026-10-08. Every trader-rfq and high-board cell on this board is after the fix.
- **high-board is v4.** Its seeded risk-run ids were literal 1–5 rather than the book's
  real ids, so its position-level evidence did not match the book. The governed valuation
  run is now seeded, step 6 states an ungoverned figure to refuse, and step 8 asks for
  its artifact. The two perfect high-board trials on this board are one Haiku trial
  (35 of 35) and one luna trial.
- **risk-manager-control is v3.** Its stale risk run pinned position ids 1–3, which are not
  the control book's positions on the live DB. The fix seeds the real ids.
- **The scorer accepts an integer sent as its decimal string.** mimo's operations row was
  re-scored under it in the earlier post (79.5 to 88.6), and re-scoring the other rows
  changed nothing; Haiku's rows were scored under it from the start.

---

## Caveats

- **Two trials per cell.** The top two OVRs are within that noise, and several models'
  two trials on one workflow differ by 8 to 14 points (luna scored 100 and 85.7 on
  high-board).
- **One effort level.** Every contestant ran at `high`. Haiku's other levels are
  unmeasured, and the gateway's acceptance of them says nothing about whether they differ.
- **Two eras on three workflows.** Haiku's three workflows ran twelve days after the trio's,
  on later app builds. The scoring is identical for the three workflows that stay on the
  earlier runs.
- **risk-manager-control was run twice, and the board uses the second pair.** The first
  pair (#148) is shown beside it and gives a different top two (Haiku 86.2, mimo 86.3). Haiku's
  re-run followed its first pair's low score; the trio's re-run was added to remove that
  asymmetry, and the trio did not score lower on it. Four Haiku trials average 89.1, and
  Haiku is the lowest of the four on this workflow either way. The figures are close, but
  not comparable, to the earlier board's.
- **Haiku's cost is partly an estimate.** Its rates are measured and matched the bill
  exactly on the one workflow billed per call; the other five are rate-verified estimates.
- **deepseek's price is not fixed.** The gateway billed it at the higher of its two listed
  prices for part of #148 and for all of #150, so its cost per match depends on when it ran.
- **Latency is not reported.** Wall-clock time depends on the gateway as much as the model.
