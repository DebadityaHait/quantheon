# Haiku 5.5 max-effort compaction investigation

Read-only investigation of Arena run **151**, completed 2026-10-10, using the live
Arena database, stored per-trial transcripts, indexed local trace queries and
offline replay of the installed compaction code. No runtime code, scores, database
rows or model settings were changed. No new live model calls were made.

## Finding

The current harness has confirmed compaction defects that disproportionately
affect max effort. The strongest causal evidence is an exact offline replay:
serialized reasoning signatures inflate the summary-input estimate; a 4,000-token
trim removes every message; the harness nevertheless advances the cutoff and
replaces the original user intent and work history with a placeholder. An
unreferenced failed artifact read then blocks further progress, causing repeated
max-effort summarization of that placeholder.

This establishes context loss and wasted computation. It does **not** establish
that compaction alone caused the entire objective-score drop. The RFQ traces also
show a completeness/input-mapping blocker before the first compaction.

## Cohort and observations

Run 151 used app SHA `5203959c4c65`, deepagents 0.7.19, langchain 1.4.2,
langchain-core 1.6.5 and langchain-anthropic 1.7.4. It contains one model,
`claude-haiku-5-5`, six workflows, five efforts and two trials per cell.
It is a single-run comparison, separate from the published high-only regroup.

| Effort | Mean objective | Mean tool calls/trial | Reasoning tokens, 12 trials | Truncated calls | Trials with compaction | Trials with empty-history placeholder |
|---|---:|---:|---:|---:|---:|---:|
| low | 93.80 | 24.42 | 49,710 | 0 | 0 | 0 |
| medium | 94.81 | 32.92 | 106,887 | 0 | 0 | 0 |
| high | 94.36 | 40.33 | 211,367 | 0 | 0 | 0 |
| xhigh | 93.25 | 53.58 | 750,624 | 1 | 0 | 0 |
| max | 83.17 | 137.67 | 8,263,388 | 33 | 12 | 12 |

The max trials contain **83 LLM summary calls**, spending **1,678,837 output
tokens**. Fourteen summaries returned blank text; fifteen reported
`stop_reason=max_tokens`. Empty-input compactions returning a fixed placeholder
do not make an LLM call, so 83 is not the total number of compaction events.
Output tokens include reasoning and must not be described as visible summary text.

The RFQ objective scores are high **90.3** and max **50.0**. The max trials scored
59.7 and 40.3, with 182 and 173 tool calls. This is a loss of objective correctness,
as well as an efficiency penalty; it is not just the EFF component lowering OVR.

## Exact failure chain: RFQ max trial 1

Evidence:

- Arena match 777; thread 1357.
- `artifacts/arena/151/trader-rfq-booking-day/claude-haiku-5-5/max/transcript.trial1.json`.
- Trace DB: `data/agent_traces.sqlite3`, table `trace_runs`, indexed by thread/start.
- Model-state span `01a123a9-92ce-7da0-8fec-37771406ada6`,
  2026-10-10 02:34:38 UTC.
- First subsequent LLM summary span `01a123aa-0516-7f41-9464-5a95e2443dc6`,
  2026-10-10 02:35:07 UTC.

### 1. Summary trimming counts bytes that its serializer does not emit

`compaction.py:365` counts `len(str(message.content)) // 4`. For Anthropic messages,
content includes opaque reasoning signatures in `extras.signature`. The same
counter is used for both the trigger and summary-input trimming.

The exact five-message eviction batch is estimated at **16,643 tokens**. The
installed `_trim_messages_for_summary` uses `strategy=last`, `start_on=human`,
and the harness's **4,000-token** budget. It returns **zero messages**.

Repeating the estimate after excluding only signatures produces **1,932 tokens**
and retains **all five messages**. The XML strings generated for the two batches
are **byte-for-byte equal**, 7,605 characters long. Thus this is an exact mismatch
between summary trimming and summary serialization, not a conjecture about the
provider tokenizer. Signatures must remain intact wherever the model wire requires
them; a summary projection/counter is a separate concern.

### 2. Empty summary input is accepted as a successful compaction

The installed LangChain summarizer returns
`Previous conversation was too long to summarize.` when trimming yields no input.
Our `_acreate_summary` delegates to it and returns that string without validating
coverage or content. Deepagents then installs the summary and advances the
absolute cutoff to **5**.

The removed prefix included the user request and the first fetch/verification
exchange. The next summary explicitly says:

> User intent: Unresolved. The wrapper contains no explicit request.

> Next action: Unresolved.

The original state and offloaded history remain available, so this is loss from
the model's active view, not deletion of all durable evidence.

### 3. A failed artifact read causes zero-progress compaction

The preserved prefix starts with an AI call to `read_artifact(section="data")`,
then its error result: `artifact section not found: data`.

`read_artifact` is protected unless it carries a validated artifact reference.
An error result has none. The error boundary returns it outside the successful
capture path. The compactable batch therefore stops before that result; the
pair-safe cutoff backs up to its AI call, leaving **only the previous summary**
as the next batch.

With a prior event, absolute cutoff is `prior_cutoff + effective_cutoff - 1`.
Here that is **5 + 1 - 1 = 5**: no additional original message is removed.
The harness still calls the summarizer and installs a new summary.

Thread 1357 records **42 LLM summary calls**, consuming **580,988 output tokens**,
while all **43 model states carrying an event have cutoff 5**. Repeated summaries
describe the placeholder and its missing context, not new task progress. This is
a confirmed compaction loop, not merely an unusually verbose model.

### 4. Summary generation inherits max effort and can return blank

The summary invocation parameters explicitly contain
`output_config={"effort":"max"}` and `max_tokens=32768`. The installed helper
uses the same model via `self.model.with_retry()` and returns `response.text.strip()`.
There is no separate summarizer reasoning policy or validation of blank/truncated
text before replacement.

For example, risk-manager max thread 1346 has 18 summary calls: eight return blank
text and eight stop at the output cap. Replacing working context with a blank
narrative is an additional confirmed failure. Increasing the output cap alone
would not repair the empty-input or zero-progress defects.

## Other contributors and limits

- Max's larger reasoning signatures and longer histories expose a defect that
  none of the lower-effort trials in this sweep reaches. This explains differential
  exposure; a matched live A/B is still needed to quantify score recovery.
- RFQ trial 1 already refuses quoting on missing `initial_price` before its first
  compaction. It passes RFQ product terms to completeness checks without reconciling
  the available `market.spot`. Later it repeatedly reports that `build_product`
  drops `initial_price`. Trial 0 prices successfully but hits the same built-product
  completeness issue. That semantic blocker needs a separate investigation.
- A fixed eight-message batch and six-message tail are unrelated to actual bytes
  removed. The current estimator also omits structured tool-call arguments and tool
  schemas. These weaken budget control, but the evidence above does not require
  assigning every score failure to these additional concerns.
- Personas use the framework's default summarizer, while the orchestrator uses
  the custom ledger compactor. They do not share a uniform compaction policy.
- The earlier duplicate-summarizer/double-slice bug was fixed before run 151.
  This investigation finds different defects in the currently installed path.

## Repair requirements

1. Estimate summary input from its actual serialization, excluding opaque signature
   metadata from that estimate. Keep wire-required signatures intact.
2. Refuse to advance the cutoff for empty-input, blank, unusable or truncated
   summaries. Preserve prior context and expose a compaction failure/recovery state.
3. Require advancement of the absolute cutoff and meaningful context reduction.
   A summary-only batch cannot count as successful compaction.
4. Give failed tool results an explicit safe policy: retain/capture the call and
   error together without permanently pinning the eviction boundary. Preserve the
   fail-closed rule for uncaptured authoritative results.
5. Give summarization its own measured reasoning/output policy, with output
   validation. Max reasoning for task execution need not imply max for compaction.
6. Add exact replay coverage for these recorded failures, then a paired live A/B
   on frozen manifests/provider/model/effort. Report objective success, context
   coverage, cutoff progress, truncation, call counts and costs.

## Verification performed

Exact recorded-message offline replays reproduced the empty trim and fixed-cutoff
behavior. Removing signatures only from the summary estimate retained the complete
batch without changing its serialized XML. The existing tests
`tests/test_long_agent_compaction.py` and `tests/test_single_summarizer.py` pass:
**11 passed**. Their passing status does not cover the failures above.
