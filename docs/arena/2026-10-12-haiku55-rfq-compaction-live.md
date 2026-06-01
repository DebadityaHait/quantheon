# Haiku 5.5 RFQ max-effort live validation — run 152

**Result: partial operation; compaction is not fully working.** Two summaries
committed and selected exact artifacts were recoverable, but duplicated manifest
rendering refused 41 of 43 summary attempts in the scored trial. Internal summary
JSON also contaminated eight stored user-facing replies. No implementation code
was changed during this run.

## Run and comparison

- Requested: `trader-rfq-booking-day`, `claude-haiku-5-5`, effort `max`, two trials.
- Executed: run **152**, match **778**. Trial 0 is thread **1358**; trial 1 is **1359**.
- Same RFQ manifest as run 151: v4,
  `edd690543298a34bea0ff623336d1de3b4cdf77f1755feb2f3730193cf188aa1`.
- Anthropic upstream: `anthropic/claude-haiku-5.5:anthropic`, ZenMux Anthropic wire.
- Execution: `output_config.effort=max`, `max_tokens=32768`.
- Summarizer: `output_config.effort=low`, `max_tokens=4096`.
- Default compaction thresholds: input fraction 0.7, token fallback 100000;
  recent messages 6; summary input limit 16000.
- App stamp: `0.2.0+5203959c4c65.dirty`. Exact working source hashes and patch
  snapshot are recorded in `outputs/haiku-rfq-compaction-validation/preflight.json`
  and `patch.diff`; hashes were checked again after completion with no drift.
- Installed distributions matched `uv.lock` at preflight. Jury and System One off.
- Run 152 completed. One scored trial is retained; trial 1 was excluded after
  Anthropic connection errors (11 errored LLM spans). This is **not** a two-trial
  score. An invalid-trial transcript is saved beside the scored transcript.

| Metric | Run 151 max trial 0 | Run 151 max trial 1 | Run 152 scored trial |
|---|---:|---:|---:|
| Objective | 59.7 | 40.3 | **64.5** |
| Passed checks | 37/62 | 25/62 | **40/62** |
| Counted tool calls | 182 | 173 | **198** |
| LLM calls | 174 | 199 | **178** |
| Reasoning tokens | 914815 | 1011895 | **694443** |
| Output tokens, including reasoning | 1013242 | 1120832 | **839499** |
| Truncated calls | 1 | 0 | **0** |

The new transcript contains 200 tool calls; the workflow's counted-call metric
excludes two, yielding 198. Use the latter for scoring comparisons.

The scored trial took 61m25s (02:29:16–03:30:41 UTC). Stored list-price cost is
**USD 2.057743 for the scored trial only**; it excludes the invalid second trial
and is not gateway billing. One scored trial cannot establish score improvement.

## What worked

1. All 43 summary LLM calls in thread 1358 used low effort and the 4096 output
   cap. None returned blank text or stopped at the cap. Summarization consumed
   **99768 output tokens**, compared with 580988 in the old worst RFQ trial.
2. No `Previous conversation was too long to summarize.` placeholder was installed.
3. Two valid compactions committed, in **different agent namespaces**:
   - Trader subagent namespace `tools:2c0bad1b-8ad4-1283-a645-430c32c6f05e`:
     cutoff **13**, five selected artifact cards.
   - Orchestrator: cutoff **29**, eight selected artifact cards.
   These are separate cutoffs, not a 13→29 sequence within one agent. No changed
   summary with a nonadvancing cutoff was found within either namespace.
4. All 13 retained artifact IDs exist in workflow 2712. Their descriptor hashes
   match the ledger; reading every retained artifact's exact bytes also verifies
   all 13 SHA-256 values. A retained artifact, **34373**, was read successfully
   after the trader compaction (**02:47:52 UTC**).
5. Runtime-rendered current-work blocks were present in the committed summaries.
   Subsequent execution proceeded without orphan-tool replay errors.

The valid summaries are trace spans
`01a12e01-9ef4-7662-8d56-726e231cd02e` and
`01a12e0c-d24a-7272-8b0b-abf461871e8c`.

## Remaining defects demonstrated live

### 1. Duplicated artifact descriptors consume the retained-context budget

`_validated_summary` renders artifacts in both `artifact_manifest` and the full
`disclosure_manifest`. Replaying every recorded summary response against the
recorded catalog reproduces **41 budget refusals and 2 accepted outputs**.

The first response (`01a12df4-19b4-7a93-8c60-63f222d25c1c`) contains:

- Narrative: 4545 characters.
- Artifact manifest: 6785 additional characters.
- Disclosure manifest: 7421 additional characters.
- Combined: 18751 characters, estimated **4687 tokens**, budget **4096**.

The model response itself was valid and complete. The runtime made it too large
by duplicating the selected descriptors. Refusal preserved original context, but
prevented most compactions. Fix by rendering one compact authoritative descriptor
set; keep full provenance in structured metadata/exact storage, and give selection
an explicit retained-reference budget before generation. Do not silently drop
selected dependencies or widen the frozen validation budget to make this pass.

### 2. The failure fingerprint does not prevent repeated refused attempts

The fingerprint covers effective conversation text. Each intervening tool/model
message changes it, so the next turn again summarizes the same mostly unchanged
prefix with the same oversized reference set. There is no stable rejected-batch
or catalog/configuration identity. Forty-one refused calls survive the intended
retry guard. A rejection should be keyed by proposed evicted prefix, selected
reference/catalog budget and summarizer configuration, with bounded retry or an
explicit recovery action.

### 3. Internal compaction JSON leaks into public replies

Eight of ten stored assistant replies in thread 1358 contain the internal JSON
fields `summary` and `retained_reference_keys`. Message IDs:
**21834, 21836, 21838, 21840, 21842, 21844, 21850, 21852**.

Example: message **21842** begins with a fenced JSON compaction summary. The trace
also contains the appropriate final execution reply (“No position was booked…”).
The saved Arena transcript extracts that final reply, while the app's stored chat
reply contains the summary, so the objective score alone hides this defect.

Summary calls inherit model-event streaming. The public collector does not isolate
`lc_source=summarization` from execution messages, and persistence prefers collected
stream text over the final graph reply. A compactor must emit an explicit internal
event scope that both v2/v3 collectors filter, including reasoning/text/completion
events. Do not solve it by detecting JSON strings in user-facing prose.

The invalid second trial also has one contaminated reply (message **21854**), but
its subsequent connection errors prevent a complete compaction evaluation.

## Other causes of RFQ failure

Trial 0 quoted the RFQ successfully at 34.19286846640912, then refused direct
booking because the built/stored product omitted `initial_price`. This reproduces
the independent completeness-versus-market-spot issue found in run 151. The agent
ran valuation/risk on the existing two-position book and correctly stated that the
new MSFT trade was absent. It did not export a ticket for a nonexistent booking.
Compaction does not resolve that semantic blocker.

## Evidence

- Scored transcript:
  `artifacts/arena/152/trader-rfq-booking-day/claude-haiku-5-5/max/transcript.trial0.json`.
- Trace analysis and retained-reference verification:
  `outputs/haiku-rfq-compaction-validation/trace-analysis.json`, `event-audit.json`.
- Reproduction scripts: `inspect.py`, `audit_events.py` in the same output directory.
- Launch output: `outputs/haiku-rfq-compaction-validation/run.log`.
- Source/configuration/environment evidence: `preflight.json`, `patch.diff`.

The rerun fulfills the live check and demonstrates that another compaction patch
is required. It does not qualify the current implementation for release.
