# Progressive compaction implementation plan

Goal: automatic and explicit user compaction with DeepAgents history offloading,
short task/progress context, and model-selected references to exact saved content.

Architecture: retain DeepAgents' event format, pair-safe retention, history files
and overflow recovery. Own preparation, summary validation and atomic event commit.
The summarizer selects keys from a workflow-scoped server catalog; the runtime
renders immutable artifact descriptors and scoped task/RFQ retrieval instructions.
Task execution model settings and wire-required reasoning signatures are preserved.

1. Add validated environment settings for context fraction/token fallback, recent
   tail, summary input/output limits and summarizer effort. Cover configuration.
2. Replace destructive hidden trimming with complete projected-batch selection.
   Separate request counting from summary XML budgeting. Validate structured summary
   output, selected references, completion status, cutoff progress and reduction.
   Retain current instructions, todos and active task state outside model prose.
3. Keep selected reference descriptors in server-owned summary metadata across
   repeated compactions. Capture disclosed tool/task/report bodies to exact artifacts;
   allow verified error receipts without allowing uncaptured financial evidence out.
   Add bounded workflow-scoped retrieval for tasks, RFQs and asynchronous task runs.
4. Install one shared compaction policy in orchestrator, personas, general-purpose
   and asynchronous agent stacks. Add `/compact` and a thread compaction endpoint;
   compact checkpoints without invoking business tools and refuse pending HITL.
5. Add adversarial regression/integration tests (signatures, empty/truncated output,
   selection spoofing, references surviving repeated compaction, error pairs,
   no-progress, manual/automatic parity, retrieval scope). Update docs/changelog.
6. Run focused runtime/API/frontend tests and the controlled paired benchmark.
   Report structural verification separately from any live model performance claim.

The user explicitly requested implementation in this session. Existing unrelated
working files remain untouched; no commit, deployment or live Arena run is implied.

## Verification

- Backend: 322 tests passed across compaction, actual checkpoint/API controls,
  artifacts, stack registration, workflow routing, streaming/HITL, async agents,
  tool capabilities, desk-workflow reservation and configuration.
- Frontend: 65 tests passed across ChatComposer and its workflow/thread controllers;
  `npx tsc --noEmit` passed. UI styling was not changed.
- Controlled paired compaction benchmark: all eight criteria passed, installed
  dependencies match `uv.lock`. Candidate exposes zero raw ground-truth payloads,
  recovers four of four exact evidence tuples, and uses 1,968 targeted read bytes
  versus 15,396 for the baseline. Evidence is in
  `/tmp/otc-progressive-compaction-ab.{json,md}`.
- Recorded Haiku replay: the previously empty five-message summary batch now
  includes the original instruction at an estimated 2,747 prompt tokens; the
  previously fixed absolute cutoff of 5 advances to 11 after the error-pair fix.
- Live Arena score improvement is not yet measured. These results establish
  structural recovery and controls, not a production model-performance claim.
