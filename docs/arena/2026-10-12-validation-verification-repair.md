# Product validation and booking verification repair

The four requested repairs are implemented locally. No new live Arena match was
launched during repair; run 153 remains failed. Historical transcripts and scores
were not changed.

## Behavior

1. `check_term_completeness` distinguishes `raw_build_inputs`,
   `native_product_terms` and `valuation_market`. Raw checks remain compatible
   with the existing synthesis contracts. Native checks use installed QuantArk
   conversion and constructor validation, including enum/date conversion. A
   returned BarrierOption passes without `initial_price`; adding that unsupported
   native argument still fails. Market checks require explicit spot/r/q/vol/date,
   validate values, and never fill missing inputs with defaults.
2. `build_product` retains supplied inputs and validation-market origin outside
   native kwargs in `product_spec.source_payload.build_provenance`. Dated fixing
   references identify a workflow-scoped captured snapshot, hash, fixing date,
   symbol, selector and retrieval method. The snapshot's exact close/date must
   match the supplied initial price; fallback/foreign/mismatched references fail.
   Booking and RFQ adapters reverify copied provenance against an exact captured
   build before persistence. Each position retains its own provenance even when
   products are reused. Compaction retains fixing dependencies of selected
   build/RFQ cards without pinning every unselected historical snapshot.
3. Exact CAS tool captures stamp server-owned operation receipts with workflow,
   thread, user-message, family, representation and input hash. The grounding
   guard recognizes current-turn persona validation across graph namespaces.
   Failed tools, stale turns, other families and explicitly different
   representations do not satisfy grounding. Exact blobs are hash-verified.
4. `verify_position_booking` reads scoped booking receipts and the target-book
   row. It compares the booking fingerprint and requested fields, producing a
   terminal confirmation/mismatch/absence/no-session-receipt verdict, or a
   specific inconclusive ambiguity. Matching historical economics do not prove
   a session booking. `PositionVerificationMiddleware` returns the exact
   terminal result for narrow confirmation requests, preventing another model
   call or delegation. Compound requests continue. All app-owned stacks carry
   the middleware. The position-snapshot procedure performs one target-book
   inventory read and then this bounded verification.

Background pricing also returns an explicit `record_reference` with
`kind='task_run'`; its legacy `task_id` field is preserved. This prevents reading
a TaskRun as an AgentTask during progressive disclosure.

Native product identity/term hashes, HITL booking requirements, and the frozen
Arena scoring manifest remain unchanged. Validation defaults are labeled as
validation defaults, not historical pricing evidence.

## Verification

**576 tests passed**, with two existing LangGraph v3 experimental-protocol
warnings. Results: `outputs/validation-verification-repair/pytest.xml`.

The focused suite covers representation/native validation, actual fixing
artifacts and scope, copied/forged provenance, product reuse, typed TaskRun
retrieval, stale and wrong-family grounding, successful and errored content
blocks, confirmed/changed/historical/ambiguous booking records, tool/stack
registration, existing RFQ/booking adapters, workflow skills, streaming, and
progressive compaction.

Real DeepAgents graph regressions establish:

- A persona calls the deterministic verification once; both persona and
  orchestrator finish without another model call after a terminal result.
- A persona native-term check grounds its returned verdict and the
  orchestrator's synthesis, with no redundant grounding nudge/delegation.

The deterministic paired compaction benchmark passes all eight predeclared
criteria, including installed-versus-lock alignment. Candidate evidence
recoveries are 4/4 and targeted disclosure is 1968 bytes. This is structural
validation, not a live-model performance claim.

Benchmark artifacts:
`outputs/validation-verification-repair/compaction-benchmark.json` and `.md`.

`git diff --check` passes. Plan:
`docs/plans/2026-10-12-validation-verification-repair.md`. New semantic/runtime
regressions: `tests/test_validation_verification_repair.py`.

## Live qualification still required

The runtime repairs remove the reproduced contradictory contract and provide a
deterministic verification exit. Whether Haiku chooses the correct new tools and
representations consistently must be checked in a fresh fixed-source smoke.
There is no new live score or claimed low/medium/max ranking improvement yet.
The historical intake/profile provenance and approval-scope detours were not
separately changed by this repair.

## Follow-up defects from live smoke #154

The match transcript shows a successful verification immediately after booking,
then a separate verification on the user's next turn. The second result was a
false `product_type` mismatch because that field was missing from the verifier's
stored-value map. These were separate user turns, not two verifier calls in the
same turn. The false mismatch response also omitted the actual stored contract,
so it could not satisfy the follow-up request to confirm the down-and-in terms.

The follow-up patch now compares and reports `product_type`, includes observed
terms in both confirmed and mismatch responses, and regression-tests that a
terminal result short-circuits another model call. It also uses booked position
currency for the `option_core` mirror, compares build provenance only on stable
inputs/native terms/fixing references and restores the captured copy, checks
unsupported families before resolving fixings, and normalizes blank RFQ adapter
currency through the underlying resolver.

Focused verification is recorded in the current patch's test output. No new live
Arena match was launched after these follow-up changes; #154 remains the latest
live smoke evidence.
