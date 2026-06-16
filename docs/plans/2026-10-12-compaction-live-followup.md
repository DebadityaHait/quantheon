# Compaction live-validation follow-up

Run 152 demonstrated duplicate descriptors, repeated rejected batches and internal
summary events contaminating public replies. Preserve its source/results as evidence.

1. Render one compact disclosure manifest; keep full selected descriptors in
   server-owned summary metadata. Give retained context and reference cards their
   own validated budgets, separate from the model output limit. Include the final
   wrapper/current-work block in retained-context validation. Preserve all selected
   keys and mandatory dependencies, refusing rather than silently dropping any.
2. Give summary selection compact candidate cards with their rendered cost and an
   explicit reference budget. Carry full descriptors across repeated compactions.
3. Persist a rejected-batch identity (prefix content/reference hash, prefix length,
   current instruction, required references, configuration). Adding messages after
   that prefix must not reissue the same expensive summary attempt. Changed work,
   selected evidence or settings can allow another attempt; manual requests retry.
4. Mark summarizer invocations as internal and suppress their public message
   events in both LangGraph v2/v3, keeping tracing/usage intact. Test public stream
   and stored reply against actual graph events, not JSON-content heuristics.
5. Replay all 43 scored run-152 summary responses against their recorded catalogs;
   retain selected keys and verify final package budgets without live calls. Run
   focused checkpoint/stream/runtime tests and update the controlled paired
   benchmark for metadata-backed disclosure, then document verification limits.

Implementation is explicitly requested. No changes to Arena scores/manifests,
RFQ semantics or historical evidence are part of this patch.

## Verification

- 331 backend tests passed across compaction/checkpoints, all agent stacks,
  streamed/persisted responses, artifact access, routing, HITL, async agents,
  tool capability registration and configuration.
- Actual DeepAgents graph tests cover both v2 and v3: one internal summary call
  is traced, its summary commits, the final execution answer survives, and no
  internal summary text reaches the public collector. Synthetic SSE persistence
  tests also verify that the stored reply contains only public execution text.
- Retry test refuses a summary once, appends another message, and confirms no
  second summary call. A changed user instruction permits another attempt.
  The child-task shared attempt record is exercised through the real async wrapper.
- `scripts/replay_compaction_summaries.py --thread 1358` replayed all 43 recorded
  run-152 responses and selections. All 43 are now accepted; no selected or
  mandatory key is removed. Largest complete wrapped package: 2989 estimated
  tokens, within the unchanged retained budget 4096. Reference budget: 2048.
  Evidence: `outputs/haiku-rfq-compaction-validation/followup-replay.json`.
- Controlled paired benchmark: all eight predeclared criteria passed, dependency
  lock alignment passed, zero raw ground-truth payloads in the candidate prompt,
  four of four exact evidence recoveries. Candidate visible retained context is
  5909 bytes across four cases versus 16981 before this follow-up, with full
  provenance still recovered from server metadata and exact storage. Evidence:
  `/tmp/otc-compaction-followup-ab.{json,md}`.
- `git diff --check` passed. No live model calls or Arena rescoring in this patch.
  Replay and graph tests establish the repaired failure paths; a fresh live Arena
  match is still needed to measure score/cost recovery after this revision.
