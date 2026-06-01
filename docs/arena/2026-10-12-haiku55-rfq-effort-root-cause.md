# Haiku 5.5 RFQ effort comparison and root cause

The principal booking blocker is a representation mismatch between the term-completeness contract and validated product output. Max repeatedly checks native product terms against raw builder-input requirements, receives `missing_required=["initial_price"]`, and refuses to book. Position verification then investigates a trade that was never booked. The position queries inspected here succeed; the orchestration after those queries is where the live verification turn stalls.

Compaction has separate real defects documented in the earlier investigation. They amplify the wasted work but do not originate this semantic contradiction: both historical max trials receive the false blocker before their first summary call.

## Controlled historical comparison

Run **151**, matches **773 / 774 / 777**, two trials per effort. Same workflow `trader-rfq-booking-day`, manifest v4 SHA-256 `edd690543298a34bea0ff623336d1de3b4cdf77f1755feb2f3730193cf188aa1`, app `0.2.0+5203959c4c65`, QuantArk 0.3.0 and DeepAgents 0.7.19. Trace invocation parameters confirm the same pinned model `anthropic/claude-haiku-5.5:anthropic`, output cap 32768 and unset temperature. The execution effort is the varying parameter. These are sequential trials, not identical full database snapshots; the product-output equality and executable counterexample isolate the representation defect separately.

| Effort | Objective scores | Counted tool calls | Elapsed minutes | Completeness checks |
|---|---|---|---|---|
| low | 95.2 / 95.2 | 43 / 43 | 3.89 / 4.40 | 1 / 5 |
| medium | 90.3 / 88.7 | 50 / 46 | 4.98 / 5.17 | 4 / 5 |
| max | 59.7 / 40.3 | 182 / 173 | 72.89 / 79.59 | 18 / 29 |

Counted calls are the stored scorer's denominator, excluding `record_answer`. Raw transcript totals are 45/46, 52/49 and 183/175, respectively. Do not compare these counts with framework-inclusive trace spans.

### Where behavior diverges

All six trials build the same seven native barrier terms: multiplier 1, exercise date 2027-07-16, strike 401.1, PUT, barrier 320.88, DOWN_IN and rebate 0. The returned `product_kwargs` and `product_spec.terms` omit `initial_price`, including in the successful low and medium trials.

Low validates the original inputs containing `initial_price=401.1` at intake and later books with reconstructed raw inputs. Medium generally follows the same route: it validates the supplied inputs, rebuilds and books. Medium trial 1 also encounters the missing-initial-price warning, yet quotes using the known market spot and subsequently books.

Max trial 0, fresh-build step **index 3**, does four builds and eight completeness checks. It alternates between original input (`complete=true`) and returned kwargs (`complete=false`). Rebuilding with the same initial price produces the same native kwargs; another check cannot resolve the apparent inconsistency. At direct-booking step **index 4**, it makes five more completeness checks and never calls `book_position`, despite the user's explicit booking instruction and confirmation.

Max trial 1 encounters the warning earlier. It checks saved draft terms at intake, then at quote step **index 1** checks them again, including a variant with nested `market.spot=401.1`. The checker still reports missing `initial_price`, so it does not quote. The fresh-build turn confirms original inputs are complete but treats the normalized product as incomplete; the booking turn again makes no booking call.

The intake trace contains the contradiction in adjacent real tool results: at **02:25:16 UTC**, `validate_rfq_terms` rejects the product carrying initial price with `Unsupported kwargs for BarrierOption: initial_price` (call `toolu_017tzmeaUcB4o1wZ2sLuw5Xm`). At **02:25:27**, removing that field makes RFQ validation succeed (call `toolu_01ELCD7YiJT9qX8wPemywq7M`), while the completeness check on those same native terms returns missing initial price (call `toolu_01JC3zHhcnNYATEQ3vgEEuN2`; exact trace span is listed below). Max is trying to obey two mutually incompatible public tool verdicts.

This is not merely loss of the original number: max trial 0 explicitly reports both the complete original input and incomplete returned product. It has the information but no coherent tool contract telling it which representation governs which operation.

The repeated validation spreads into unrelated later tasks. In the book-repricing turn (**index 6**), max trial 1 makes **14 completeness checks**, although that turn asks for batch pricing under the named profile. Low and medium make none there. A previous blocker has become the dominant task across subsequent turns.

### The blocker precedes compaction

| Max trial | First missing-initial-price check | First summary call |
|---|---|---|
| 0, thread 1356 | 2026-10-10 01:42:35 UTC, span `01a12379-eb5f-75a3-92aa-eec4abd01bb1` | 01:49:22 UTC, span `01a12380-20e9-79e1-819e-6f3495f1b84c` |
| 1, thread 1357 | 2026-10-10 02:25:27 UTC, span `01a123a1-2b66-7d03-934e-7dfbf926d6c5` | 02:35:07 UTC, span `01a123aa-0516-7f41-9464-5a95e2443dc6` |

Low and medium make no summary calls in these six-trial comparison data. This ordering rules out compaction as the origin of the first false completeness verdict. It does not rule out later compaction amplifying scope drift or repetition.

Separating trace usage confirms both problems. Historical max execution alone consumes **832670 / 472184 reasoning tokens**, versus **6779 / 8195** for low and **13141 / 12706** for medium. Max summarization adds another **82145 / 539711 reasoning tokens**. Compaction repair removes a major additional cost; the execution loop remains independently expensive. Counts are summed provider-reported usage, not a measurement of private reasoning content.

## Independent code reproduction

Using the installed native QuantArk and current application services, with no LLM and no business-state writes:

```python
terms = dict(initial_price=401.1, strike=401.1, barrier=320.88,
             barrier_type="DOWN_IN", option_type="PUT",
             exercise_date="2027-07-16", rebate=0.0,
             contract_multiplier=1.0)
built = build_product("BarrierOption", terms, underlying="MSFT", currency="USD")
```

| Operation | Actual result |
|---|---|
| Build from original terms | `ok=true`, native validation succeeds |
| Check original terms | `complete=true` |
| Check returned product kwargs | `complete=false`, missing `initial_price` |
| Check returned kwargs plus `market.spot=401.1` | Same missing field |
| Check returned kwargs plus top-level `initial_price=401.1` | `complete=true` |
| Normalize returned native terms for booking | Accepted unchanged |
| Inspect native `BarrierOption` constructor | No `initial_price` parameter |
| RFQ validation with native terms and explicit market | `valid=true` |
| Same RFQ with `initial_price` added to product terms | `valid=false`, unsupported constructor argument |

The normalization check proves acceptance by the product booking gate; it does not create a position or certify every other booking condition.

Code locations explain the contradiction:

- `backend/app/services/domains/product_contracts.py:97` describes one field as both “Initial fixing S0 / valuation spot.” At line 164, scalar-option raw input requirements include it; BarrierOption inherits them.
- `backend/app/services/domains/product_builders.py:423` validates raw `initial_price`, then emits the native constructor kwargs without it. The barrier builder inherits this behavior. `BuildResult.product_kwargs` aliases normalized `product_spec.terms`.
- `backend/app/tools/term_completeness.py:100` checks the synthesis input aliases. Its public description promises enough completeness to price/book without identifying the representation, and line 167 says every missing input must be collected before pricing/booking.
- `backend/app/services/domains/booking.py:92` already explains that initial price is a validation spot rather than a native scalar-option product term. At line 153, booking validates prebuilt terms through the native builder path and accepts the returned output.
- `backend/app/services/rfq.py:44` limits raw-input synthesis to three structured families. Barrier RFQs take the native-terms validation path, so the RFQ validator correctly rejects a nonnative `initial_price` argument even though the generic completeness checker requires it.

The native omission is intentional. Blindly inserting `initial_price` into the constructor would introduce a new error. The defect is presenting an input-completeness verdict as a universal product/booking validity verdict and losing the separate fixing/market provenance carrier at that interface.

## Why position verification looks broken

Current rerun **153**, thread **1360**, executes the follow-up compaction patch. Position-verification root `01a12ec2-2214-7041-a081-7995619d1916` runs **06:17:17–06:32:21 UTC**, **15m04s**, with 31 LLM spans and 64 framework-inclusive tool spans.

1. First trader delegation, **06:17:36**, already states no booking occurred. Successful position queries return the two seeded AAPL/NVDA positions in portfolio 2, with no MSFT trade. The secondary Default-book query finds older MSFT position 22.
2. The persona's synthesis call, **06:18:29**, consumes 32768 output tokens and stops at `max_tokens`. Its visible answer nevertheless correctly states no MSFT barrier in portfolio 2, and that Default position 22 predates this thread. No tool call was severed in that response.
3. Instead of finishing the requested existence/identity check, the orchestrator delegates again at **06:21:11**, requesting all fields and provenance of the old Default trade, additional RFQ linkage and completeness checks.
4. At **06:28:41**, `TermGroundingMiddleware.after_model` bounces the orchestrator for an allegedly ungrounded completeness verdict. The persona already holds/calls the grounding tools in its separate graph namespace. The orchestrator's message scan sees `task`, artifact reads and saved-record reads; it does not recognize a scoped receipt for the persona's actual grounding check.
5. At **06:29:38**, a third delegation changes the task to comparing term sets. It labels Set A “requested new booking” but explicitly says `initial_price: NOT PROVIDED (leave absent)`, despite the known fetched 401.1. Set B copies the old trade with null initial price and a redundant `expiry_date` alias, which creates an additional raw-input lifecycle conflict.

The guard is deliberately once per turn in each stack; this evidence does not prove an infinite guard loop. It proves an unnecessary extra delegation and renewed focus on the same representation mismatch after sufficient position-query evidence already existed.

## Additional amplifiers and limits

Max trial 0 stalls during intake even before this blocker: it demands historically dated rate/dividend/volatility provenance from an OHLC snapshot and disputes profile-creation dates. Low/medium use configured defaults for drafting and the requested profile for quoting. The approval turn also expands into artifact/filesystem/queue searches despite a stored `pending_approval` status. These are additional evidence-scope problems, so fixing `initial_price` alone is not proven sufficient for max to match low/medium performance.

Low/medium success is not full semantic certification. Low trial 1 also redirects position verification into completeness and fails to confirm the stored record. Low trial 0 exposes a CNY/USD currency default discrepancy. Lower effort sometimes proceeds past contradictions; that is not a sound repair.

The new compaction rerun is a different harness snapshot from run 151. Its partial results corroborate the continuing semantic loop but are not a controlled low/medium/max comparison or proof of score improvement. Its final score must be reported only after completion.

Two later live calls also expose an ID-type ambiguity: batch pricing returns `task_id=445/446`, referring to rows in `task_runs`, but the persona calls `read_saved_record(kind="task", record_id=445/446)`, which looks in `agent_tasks`. Both reads fail. These are valid completed TaskRuns, not AgentTasks. The compact catalog can label the receipt as `task_run`, but the generic domain-output name still invites the wrong retrieval kind. A typed record reference and exact retrieval method should accompany each ID. This is a separate progressive-disclosure integration issue; it does not explain historical run 151's first completeness blocker.

## Recommended repair order

1. Separate validation of **raw synthesis inputs**, **native product terms**, and **valuation-market inputs**. Return representation-specific verdicts and the validated input/provenance reference. A native product should not fail merely because it omits a validation spot the constructor cannot accept.
2. Preserve the fixing snapshot/date, supplied initial price and resolved strike/barrier provenance separately from native constructor kwargs. Keep actual contractual S0 inside the product for families whose native contracts require it. Compaction should retain the relevant IDs and short representation labels, with exact retrieval available.
3. Let the grounding guard recognize server-owned, current-turn persona validation receipts tied to family, representation and exact input hash. Retain grounding checks; do not bypass them on the strength of unverified narrative summaries.
4. Keep verification bounded to the requested operation. Once booking receipts and target-book queries show no session booking, report that outcome. Reopen validation only for a new input or a specific unresolved discrepancy, rather than repeatedly rebuilding identical inputs or auditing an unrelated historical trade.
5. Re-run all three efforts on one fixed source snapshot and compare booking correctness, complete coverage, provenance, repetitions, latency and compaction acceptance. Keep the current scoring manifest frozen.

## Reproducible evidence

Historical source transcripts remain unchanged under `artifacts/arena/151/trader-rfq-booking-day/claude-haiku-5-5/{low,medium,max}/transcript.trial{0,1}.json`.

Extraction script `outputs/haiku-rfq-effort-comparison/analyze.py` reads both SQLite databases in read-only mode, hashes the six transcripts, extracts exact build/check/book calls, records root durations and first-summary ordering, and executes the native counterexample. Output: `outputs/haiku-rfq-effort-comparison/comparison.json`.

```sh
PYTHONPATH=backend OPEN_OTC_ENV_FILE='' .venv/bin/python \
  outputs/haiku-rfq-effort-comparison/analyze.py
```

Live compaction monitoring: `outputs/haiku-rfq-compaction-followup-live/trace-analysis.json`; launch/configuration/source snapshot: `preflight.json`, `patch.diff`, `run.log` in the same directory. This investigation does not alter runtime code midrun.

At **2026-10-12 06:50:16 UTC**, run 153 remains running, trial 0 at user turn 8/10. Audit finds **16 committed summary events**, **85 unique retained artifact references** with matching descriptor and exact-content hashes, advancing cutoffs within each namespace, and current-work blocks present. All 21 summary calls use low effort / 4096 output tokens. There are **0 budget refusals, 0 blank summaries, 0 placeholder states, 0 detected summary-JSON leaks and 0 errored LLM spans**. Four distinct selections are refused because the selected IDs are absent from that call's supplied catalog; some refer to older artifacts mentioned in prose but outside the supplied catalog, so this should not be described simply as invented nonexistent IDs. There are two truncated execution calls. These are partial observations, not final acceptance or score qualification.

At **2026-10-12 06:55:56 UTC**, the user requested immediate termination. Launcher process 62684 and watcher 71119 were killed and verified absent. Arena run 153 and launcher TaskRun 444 are **failed**, with `cancel_requested=1` retained to prevent automatic resumption. The run stopped during trial 0 at user turn 9/10; no aggregate match or score was recorded. Final snapshot: `outputs/haiku-rfq-compaction-followup-live/final-status.json`. Earlier observations above remain partial evidence; the watcher is no longer running.
