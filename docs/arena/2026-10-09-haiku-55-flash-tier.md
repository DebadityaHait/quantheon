# 🏆 OTC Desk Agent Arena — Claude Haiku 5.5 joins the flash tier

**Claude Haiku 5.5 posts the highest card of four flash models, but not by enough to call
it a win. Where it is clearly ahead is efficiency: it reaches the answer in 34 tool calls a
match, where the others need 40 to 76.**

*2026-10-09 · 4 models × 6 workflows × 2 trials · every contestant pinned to `high`
reasoning effort · output budget unpinned · objective-only scoring (jury off) ·
**48 of 48 trials scored, zero invalid** · cost is the amount **billed** by the gateway
for three models and a rate-verified estimate for Haiku*

---

## The field

| Model | Lab | Route |
|---|---|---|
| **claude-haiku-5.5** | Anthropic | `anthropic/claude-haiku-5.5`, pinned to Anthropic's own upstream |
| **gpt-6-luna** | OpenAI | `openai/gpt-6-luna` |
| **mimo-v2.6-flash** | Xiaomi | `xiaomi/mimo-v2.6-flash` |
| **deepseek-v4.1-flash** | DeepSeek | `deepseek/deepseek-v4.1-flash`, pinned to DeepSeek's own upstream |

Three of these are the models from our [earlier flash-tier board](2026-09-27-run143-flash-trio.md).
Haiku 5.5 is the new entrant. All four worked the same six desk days, twice each: a
risk-limit breach, an operations and settlement day, a risk-manager control day, a board
portfolio review, a trader's RFQ from intake to booking, and a morning of counterparty
confirmations read from PDFs and scans.

Before Haiku ran, we checked that it can read an image-only scan (three of three reads of
a scanned confirmation returned the underlying, the strike and the full reference
correctly), since one of the workflows depends on it.

---

## Headline

Consolidated card: the mean of each model's six workflow cards.

| Model | **OVR** | GRD | ADH | SYN | PRC | **EFF** | **CON** | Objective | Tool calls / match |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **claude-haiku-5.5** | **87.5** | 94 | 96 | 99 | 93 | **59** | 86 | 94.8 | **34** |
| **mimo-v2.6-flash** | 86.3 | 94 | 95 | 99 | 96 | 49 | 88 | 95.9 | 57 |
| **gpt-6-luna** | 84.3 | 93 | 95 | 94 | 96 | 45 | 86 | 95.7 | 40 |
| **deepseek-v4.1-flash** | 81.5 | 96 | 96 | 97 | 95 | 14 | 88 | 96.5 | 76 |

- **Haiku is first, without a significant margin.** Its 87.5 is 1.2 points ahead of
  mimo's 86.3, which is inside the noise of two trials per cell. We read the top of this
  board as a tie between Haiku and mimo, with luna close behind.
- **Haiku's efficiency is clearly higher than the others'.** EFF is 59, against 49 for
  mimo, 45 for luna and 14 for deepseek. It averages 34 tool calls a match, where mimo
  makes 57, luna 40 and deepseek 76. This is the whole of its card advantage.
- **It is not the most accurate.** Haiku's objective score, the share of checks passed, is
  the lowest of the four (94.8, against 95.7 to 96.5). deepseek is last on the card and
  first on the work: the best objective score and grounding, and an efficiency of 14
  because it makes more than twice Haiku's tool calls.

---

## Workflow by workflow

Objective score, with the two trials in brackets, then CON.

| Workflow | claude-haiku-5.5 | gpt-6-luna | mimo-v2.6-flash | deepseek-v4.1-flash |
|---|:--:|:--:|:--:|:--:|
| risk-limit-breach | 97.3 (94.7 / 100) · 92 | 97.4 (97.4 / 97.4) · 86 | **100.0** (100 / 100) · 99 | **100.0** (100 / 100) · 99 |
| ops-settlement | 94.3 (97.7 / 90.9) · 79 | **95.5** (90.9 / 100) · 73 | 88.6 (88.6 / 88.6) · 82 | 90.9 (88.6 / 93.2) · 86 |
| risk-manager-control | 93.6 (92.3 / 94.9) · 79 | 97.4 (97.4 / 97.4) · 99 | **100.0** (100 / 100) · 82 | 97.4 (97.4 / 97.4) · 92 |
| high-board | 95.7 (100 / 91.4) · 73 | 92.8 (100 / 85.7) · 59 | **97.1** (97.1 / 97.1) · 92 | **97.1** (97.1 / 97.1) · 96 |
| trader-rfq | 91.1 (90.3 / 91.9) · 96 | 94.3 (93.5 / 95.2) · 99 | 92.8 (88.7 / 96.8) · 79 | **95.2** (93.5 / 96.8) · 69 |
| confirmation-desk | 97.0 (97 / 97) · 99 | 97.0 (97 / 97) · 99 | 97.0 (97 / 97) · 92 | **98.5** (97 / 100) · 89 |

Workflow cards, OVR · EFF:

| Workflow | claude-haiku-5.5 | gpt-6-luna | mimo-v2.6-flash | deepseek-v4.1-flash |
|---|:--:|:--:|:--:|:--:|
| risk-limit-breach | 94 · 85 | 85 · 49 | **99 · 99** | 83 · 0 |
| ops-settlement | **89** · 80 | **89** · 82 | 83 · 65 | 75 · 0 |
| risk-manager-control | **84** · 31 | 80 · 0 | 83 · 14 | 83 · 8 |
| high-board | 91 · 95 | 86 · 93 | **94** · 89 | 86 · 40 |
| trader-rfq | 80 · 15 | **83** · 27 | 78 · 14 | 81 · 31 |
| confirmation-desk | **87** · 47 | 83 · 20 | 81 · 11 | 81 · 6 |

Correctness is close to saturated: the best and worst objective means are 1.7 points apart.
Haiku has the best card on three workflows (ops-settlement, tied with luna;
risk-manager-control; confirmation-desk) while trailing the field on the objective score
of risk-manager-control (93.6, against 97.4 to 100).

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

The pattern is clearest on the confirmation desk: 18 calls for a morning of PDFs and scans,
against 44 for luna and about 140 for mimo and deepseek. Haiku sits at or near par on
three more workflows, and on high-board it uses fewer calls than par. Its two heavy workflows
are trader-rfq (64 calls against a par of 35, where all four models overshoot) and
risk-manager-control (40 against 24, the fewest of the four).

### How it gets there

We read the transcripts of the same 48 trials to see where the saved calls come from. Four
measures, per match, averaged over the six workflows:

| Measure | claude-haiku-5.5 | gpt-6-luna | mimo-v2.6-flash | deepseek-v4.1-flash |
|---|:--:|:--:|:--:|:--:|
| Model rounds (calls to the model) | **62.9** (1st) | 72.4 | 89.8 | 89.2 |
| Repeated identical tool calls | **8.7** (1st) | 10.5 | 11.2 | 21.1 |
| Tool calls before the step's expected tool | 1.57 (2nd) | 2.58 | **1.49** | 2.51 |
| Reasoning tokens (thousands) | 15.7 (2nd) | **13.4** | 33.1 | 34.6 |

- **Fewer rounds.** Haiku makes the fewest model calls on five of the six workflows: 13%
  fewer than luna and about 30% fewer than mimo and deepseek.
- **Fewer wasted calls.** It repeats the same call with the same arguments least often. The
  margin over luna and mimo is small; deepseek repeats a call 2.4 times as often.
- **A quicker route to the right tool.** For each step the workflow names the tool it should
  use. Haiku makes about 1.6 calls before reaching it, against about 2.5 for luna and
  deepseek. mimo is level with it (1.5).
- **Light reasoning.** Haiku spends about as many reasoning tokens as luna, and less than
  half as many as mimo and deepseek.

Taken together, Haiku reaches the answer in fewer rounds, wastes fewer calls getting there,
and does not buy that with extra reasoning. That is a reading of the transcripts, not a
tested explanation, and the margins over the second-placed model are small on three of the
four measures.

Two things it does not do: it does not use fewer tokens overall (its input is 60% above
luna's, because each round carries a larger context), and it does not make fewer errors
(about one failed tool call a match, like luna). Its economy is in rounds, not in tokens.

### One example: it knows when not to act

On the operations day, the last step asks the agent to reopen a snowball whose knock-out
was recorded that morning, while the settlement it generated is still pending. The correct
move is to try, be refused by the desk, and report that nothing was recorded. Haiku
attempted the reopen, was refused, and reported that it was not recorded, in **both**
trials, and it never voided the pending settlement. luna did so in one of two trials. mimo
never refused, and cancelled the knock-out and voided the 512,500 CNY settlement both times.
deepseek declined without attempting the call in one trial and reopened in the other.

### Where it gives points back

- **It skips skill reads.** On risk-manager-control it missed the `read-risk-result` skill
  in every trial, and `run-risk` in most.
- **It overrides a desk adjustment.** On ops-settlement, cashflow 9302 was stale because
  the upstream print had been corrected after ops had manually adjusted the amount to
  91,000. The workflow scores keeping the desk's number. In both trials Haiku adopted the
  re-derived 90,000 instead.
- **Its trader-rfq trials are scattered.** Haiku scored 91.1, the lowest of the four on
  that workflow: it skipped the submit-for-approval step in one trial, and missed an answer
  and an unsupported-family check in the other.

---

## What it costs

Every figure below is priced on one list (2026-10-09), so the columns compare like with
like. For luna, mimo and deepseek we also looked up what the gateway billed on every call.
Haiku was billed call by call on one workflow of six.

| Workflow | claude-haiku-5.5 | gpt-6-luna | mimo-v2.6-flash | deepseek-v4.1-flash |
|---|:--:|:--:|:--:|:--:|
| risk-limit-breach | $0.109 | $0.069 | $0.062 | $0.156 |
| ops-settlement | $0.115 | $0.063 | $0.092 | $0.140 |
| risk-manager-control | $0.438 | $0.142 | $0.175 | $0.206 |
| high-board | $0.102 | $0.065 | $0.076 | $0.101 |
| trader-rfq | $0.263 | $0.156 | $0.217 | $0.172 |
| confirmation-desk | $0.119 | $0.074 | $0.250 | $0.288 |
| **Twelve matches** | **$1.14** | **$0.57** | **$0.87** | **$1.06** |

- **Haiku is not the cheap one.** It costs about twice luna, 31% more than mimo and 8% more
  than deepseek. Its list rate is low ($0.10 in, $0.50 out per million tokens), but it
  carries a large prompt on every call, and cache writes, which the price list omits
  ($0.125 per million tokens, measured from the gateway's billing), add up.
- **Haiku's figure is mostly an estimate, and where we could check it, it was exact.** One
  workflow was billed call by call, and the estimate matched the bill to the sixth
  decimal. The other five are estimates from the same measured rates.
- **luna and mimo are billed exactly as the list says.** deepseek's bill was $0.98 against
  $1.06 at its lower listed price: the gateway has charged deepseek either of its two
  listed prices at different times, so its cost per match depends on when it ran.

---

## Caveats

- **Two trials per cell.** The top two OVRs are within that noise, and several models'
  two trials on one workflow differ by 8 to 14 points (luna scored 100 and 85.7 on
  high-board).
- **One workflow was run twice for every model**, and this board uses the second pair. On
  the first pair Haiku is second, 0.1 behind mimo. That is why we call the top a tie.
- **One effort level.** Every contestant ran at `high`. Haiku's other levels are
  unmeasured, and the gateway's acceptance of them says nothing about whether they differ.
- **EFF is relative to each workflow's par**, and counts tool calls; rounds and tokens are
  reported separately above. A model can be efficient in calls and still spend heavily per
  call, as Haiku's cost shows.
- **Latency is not reported.** Wall-clock time depends on the gateway as much as the model.
