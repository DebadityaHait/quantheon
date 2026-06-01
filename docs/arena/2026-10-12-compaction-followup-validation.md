# Compaction follow-up verification after run 152

The patch addresses the three live harness defects recorded in
`2026-10-12-haiku55-rfq-compaction-live.md`. It does not change run 152's evidence,
scores or RFQ completeness semantics.

## Changes

Visible context contains one compact `disclosure_manifest`: keys, ids, short
summaries and locators. Retrieval instructions are shared once. Complete hashes,
timestamps and structural descriptors remain in server-owned summary metadata
and the scoped artifact store, available on later compactions and exact reads.

Summary generation output (4096 tokens), retained package (4096), and reference
subset (2048) are independent settings. The final wrapper/current-work block is
included in retained validation. Selection receives compact cards with estimated
retained costs and an explicit budget; invalid/oversized selections are refused,
never silently truncated or missing mandatory dependencies.

Rejected attempts use the proposed prefix and its references, mandatory work,
current instruction/todos and configuration, rather than the whole growing tail.
The request-local identity is shared across DeepAgents' async child tasks.

Internal summaries are tagged and scoped for both v2/v3 public-event filtering.
Summary tracing and usage metering are preserved. No response-content heuristic
is used to hide JSON; execution JSON remains legitimate public content.

## Recorded-response replay

Replayed the same 43 summary responses and full recorded catalogs from scored
thread 1358. No generation or second selection was performed.

| Measure | Run 152 renderer | Follow-up renderer |
|---|---:|---:|
| Accepted responses | 2/43 | **43/43** |
| Rejected for retained budget | 41/43 | **0/43** |
| Retained package budget | 4096 | **4096** |
| Largest accepted follow-up package | — | **2989 estimated tokens** |
| Selected/mandatory keys preserved | — | **43/43 cases** |

Replay command, from the repository root:

```sh
OPEN_OTC_ENV_FILE='' PYTHONPATH=backend .venv/bin/python \
  scripts/replay_compaction_summaries.py --thread 1358 \
  --out outputs/haiku-rfq-compaction-validation/followup-replay.json
```

## Runtime verification

331 backend tests passed. Actual DeepAgents v2/v3 graph tests commit a summary
and retain the final execution answer while emitting no internal summary text.
They also assert that the internal LLM call still reaches the tracing callback.
Stream/persistence tests reject marked summary events and keep the public answer.

The retry regression records one refused attempt, appends tail content and proves
no new summary call; changing the user instruction permits another attempt.
Other checks cover unchanged full descriptor metadata, repeated compaction,
mandatory task references, explicit reference refusal and final-wrapper budgets.

The controlled paired benchmark passes all eight criteria with lock alignment.
Visible retained context across four candidate cases falls from 16981 to 5909
bytes; exact evidence recoveries remain 4/4 and targeted recovery remains 1968
bytes. This benchmark measures structural guarantees, not live model performance.

No new live Arena score is claimed. The standalone RFQ `initial_price` issue
remains separate.
