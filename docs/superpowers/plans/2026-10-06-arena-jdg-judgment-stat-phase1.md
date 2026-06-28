# Arena JDG Judgment Stat — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute, persist, backfill and display an advisory JDG (judgment) stat — waste, selection, calibration — beside EFF, rename the jury score to SBJ, label trap steps, and run the predeclared validation that decides phase 2.

**Architecture:** A pure module (`arena/process_metrics.py`) turns a trial's transcript steps + its workflow into a raw-evidence record (counts only). `task.py` stores it per trial at write time; a backfill script adds it to historical rows. `scoring.py` turns the counts into sub-scores and JDG on read, placed at the card's TOP LEVEL (advisory, beside `sbj` and `con`) so OVR, tie-break, position and every exporter are untouched. A validation package under `scripts/arena_jdg_validation/` runs the held-out tests.

**Tech Stack:** Python 3.11, pydantic v2, SQLAlchemy/SQLite, pytest; React 19 + TypeScript + vitest.

**Spec:** `docs/superpowers/specs/2026-10-06-arena-jdg-judgment-stat-design.md`

**Worktree:** `/Users/fuxinyao/ootc-jdg` (branch `arena-jdg-judgment-stat`). Run everything with cwd = the worktree. Backend tests: `.venv/bin/python -m pytest …` (pyproject sets `pythonpath=["backend"]`, so tests import the WORKTREE code; ignore Pyright "unknown attribute" noise for worktree-new symbols — the venv `.pth` points Pyright at main). Frontend: `cd frontend && npm test -- --run <file>`; type-check `npx tsc --noEmit`. Never run the suite with a real `.env` dependence — `tests/conftest.py` already blanks `OPEN_OTC_ENV_FILE`.

## Global Constraints

- Scheme id stored in every record: `"jdg-v1"`.
- `WASTE_ZERO = 0.30` — W = max(0, 1 − waste_rate / 0.30). Predeclared; never tuned.
- K = clamp((R − 0.5) / 1.5, 0, 1). Predeclared; never tuned.
- JDG = round(99 × C × mean(defined W, S, K)); C = `scoring._correctness(axes)`; all undefined → `None` (never 0).
- Phase 1: JDG is **not** in `_OVR_WEIGHTS`, `_CARD_TIEBREAK_PRIORITY`, `_card_position`, or `card["stats"]`. OVR, tie-break key, position and `stats` of every card are byte-identical to today.
- Old card key `"jdg"` (jury) is renamed `"sbj"`; the key `"jdg"` now holds the new stat.
- Counted calls = transcript `tool_calls` (the harvest already excludes `task`, `read_file`, `write_todos`).
- Write call = `deep_agent.hitl._RISK_LEVEL_BY_TOOL.get(name) in {"write", "irreversible"}`.
- Steps are matched to the manifest by index AND identical `user` text; S and K use matched steps only; W uses all steps.
- Trap labels (0-indexed): high-board 5; ops-settlement 1, 7; risk-manager-control 7; trader-rfq 9; risk-limit-breach 4; confirmation-desk 6. Each of the six manifests bumps `manifest_version` by 1.
- The no-fs ablation switch (`OPEN_OTC_ARENA_ABLATION`) must NOT be ported to this branch.
- Backfill only ADDS `process`; it must never change any existing key. `--write` on the LIVE DB requires a fresh backup and the user's explicit go-ahead in-session.

## Review Focus

1. A tool call whose result is missing from `tool_results` (severed / malformed call) — expect: not counted as a dead search, no crash. → Task 3 test `test_missing_result_is_not_dead`.
2. A transcript with more or fewer steps than the manifest (truncated run, extra turn) — expect: extra steps unmatched, no IndexError. → Task 3 test `test_step_count_mismatch`.
3. Tool `args` that are not a dict (a JSON string from a model that stringifies args, or `None`) — expect: canonicalised safely, still comparable for repeats. → Task 3 test `test_non_dict_args`.
4. A stored breakdown whose `process` is `{"unavailable": "..."}` or absent — expect: `card["jdg"] is None`, card otherwise unchanged. → Task 4 test `test_unavailable_process_gives_none`.
5. A historical match with a malformed aggregate (non-dict trial, `n_trials` ≠ len) — expect: backfill skips it, writes nothing, reports it. → Task 7 test `test_backfill_skips_malformed_aggregate`.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/services/arena/process_metrics.py` (new) | Pure: transcript steps + workflow → raw `process` record. Owns accepted-set, write, dead-search, matching rules. |
| `backend/app/services/arena/scoring.py` (modify) | Sub-score formulas, `jdg_stat`, card `jdg`/`sbj`, trial fold. |
| `backend/app/services/arena/store.py` (modify) | `_derive_card` passes `process` through. |
| `backend/app/services/arena/task.py` (modify) | Attach `process` per trial at write time; feed it to the write-time card. |
| `backend/app/golden_workflows/schema.py` (modify) | `Step.trap: bool = False`. |
| `backend/app/golden_workflows/definitions/*.md` (modify ×6) | Trap labels + `manifest_version` bumps. |
| `scripts/backfill_process_metrics.py` (new) | IO shell around `process_metrics.backfill_breakdown` (pure core lives in the module for testability). |
| `scripts/arena_jdg_validation/` (new) | `extract.py`, `stats.py` (pure, tested), `analyze.py`, `README.md`. |
| `frontend/src/lib/arenaApi.ts`, `frontend/src/routes/Arena.live.tsx` (modify) | `sbj` type; advisory JDG chip. |
| Tests | `tests/test_process_metrics.py`, `tests/test_golden_trap_labels.py`, `tests/test_backfill_process_metrics.py`, `tests/test_jdg_validation_stats.py` (new); `tests/test_arena_scoring.py`, `tests/test_arena_api.py`, `tests/test_arena_store.py`, `tests/fixtures/arena_run94_breakdowns.json`, `frontend/src/routes/Arena.live.test.tsx` (modify). |

---

### Task 1: Rename the jury card key `jdg` → `sbj`

**Files:**
- Modify: `backend/app/services/arena/scoring.py` (`card_from_axes` return dict; `aggregate_card_from_trials`; comments at the `_OVR_WEIGHTS` / tie-break definitions)
- Modify: `backend/app/services/arena/task.py:657-658` (comment)
- Modify: `frontend/src/lib/arenaApi.ts:105`
- Test: `tests/test_arena_scoring.py` (lines ~503, 606-611, 663-704), `tests/test_arena_api.py:533-536`, `tests/test_arena_store.py` (lines ~809, 863, 898, 923), `tests/fixtures/arena_run94_breakdowns.json` (35 occurrences), `frontend/src/routes/Arena.live.test.tsx` (lines ~102, 496-571)

**Interfaces:**
- Produces: card dicts carry `"sbj": float | None` (jury value, unchanged semantics); no `"jdg"` key yet (Task 4 adds the new one).

- [ ] **Step 1: Update the tests to the new key (they become the failing tests)**

In `tests/test_arena_scoring.py` replace every jury-card `jdg` with `sbj`:
```python
    assert card["sbj"] == 42.0
```
```python
def test_card_sbj_excluded_from_ovr():
    axes = {"grounding": {"passed": 5, "total": 10}, "adherence": {"passed": 5, "total": 10},
            "synthesis": {"passed": 1, "total": 2}, "procedural": {"passed": 2, "total": 4}}
    a = scoring.card_from_axes(axes, 11, 11, judged=0.0)
    b = scoring.card_from_axes(axes, 11, 11, judged=99.0)
    assert a["ovr"] == b["ovr"]
```
```python
def _trial_card(ovr, sbj=None):
    return {"ovr": ovr, "stats": {"GRD": ovr, "ADH": ovr, "SYN": ovr,
                                  "PRC": ovr, "EFF": ovr}, "sbj": sbj}
```
```python
    agg = scoring.aggregate_card_from_trials(
        [_trial_card(80, sbj=70), _trial_card(70, sbj=None), _trial_card(75, sbj=90)])
    assert agg["sbj"] == 80.0        # mean of the non-null 70, 90
    assert scoring.aggregate_card_from_trials(
        [_trial_card(80), _trial_card(70)])["sbj"] is None
```
In `tests/test_arena_api.py` (~line 533):
```python
        # Ability card stamped at write time (spec B7); jury-off → sbj None.
        assert set(bd["card"]["stats"]) == {"GRD", "ADH", "SYN", "PRC", "EFF"}
        assert isinstance(bd["card"]["ovr"], int)
        assert bd["card"]["sbj"] is None
```
In `tests/test_arena_store.py` and `tests/fixtures/arena_run94_breakdowns.json`: replace the card key `"jdg"` with `"sbj"` (fixture: `sed -i '' 's/"jdg":/"sbj":/g' tests/fixtures/arena_run94_breakdowns.json`; then `grep -c '"jdg"' tests/fixtures/arena_run94_breakdowns.json` must print 0).
In `frontend/src/routes/Arena.live.test.tsx`: replace `jdg: null` with `sbj: null` in every card fixture.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_arena_scoring.py -k "sbj or trial" -q`
Expected: FAIL with `KeyError: 'sbj'`.

- [ ] **Step 3: Rename in `scoring.py`**

In `card_from_axes`, the return becomes:
```python
    return {"ovr": ovr, "stats": stats, "sbj": judged,
            "position": _card_position(stats)}
```
In `aggregate_card_from_trials`:
```python
    sbjs = [c["sbj"] for c in trial_cards if c.get("sbj") is not None]
    return {"ovr": blend_ovr(base_mean, con),
            "base_ovr": round(base_mean),
            "con": con,
            "stats": stats,
            "sbj": round(sum(sbjs) / len(sbjs), 1) if sbjs else None,
            "position": _card_position(stats)}
```
Comments: `# OVR weights (spec B2). Sum to 1.00. SBJ (the jury score, formerly JDG) is NOT here (advisory, out of OVR).` and `# Card tie-break priority (spec B5): GRD → ADH → SYN → EFF → PRC. Never SBJ or JDG.`
In `task.py:657-658`: `# tool-call count, SBJ advisory (the jury score, None when off).`
In `frontend/src/lib/arenaApi.ts:105`: `sbj: number | null;` with comment `// Subjective (jury) score, formerly "jdg". Advisory; never in OVR.`

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_arena_scoring.py tests/test_arena_api.py tests/test_arena_store.py -q`
Expected: PASS.
Run: `grep -rn "\"jdg\"\|'jdg'\|\.jdg\b\|jdg:" backend/app frontend/src tests scripts docs/arena/deploy --include=*.py --include=*.ts --include=*.tsx --include=*.json`
Expected: no output.
Run: `cd frontend && npm test -- --run src/routes/Arena.live.test.tsx && npx tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/arena/scoring.py backend/app/services/arena/task.py frontend/src/lib/arenaApi.ts tests/ frontend/src/routes/Arena.live.test.tsx
git commit -m "refactor(arena): rename the jury card score jdg -> sbj (frees JDG)"
```

---

### Task 2: `Step.trap` and the seven trap labels

**Files:**
- Modify: `backend/app/golden_workflows/schema.py:319-329` (`Step`)
- Modify: the six `backend/app/golden_workflows/definitions/*.md` manifests
- Test: `tests/test_golden_trap_labels.py` (new)

**Interfaces:**
- Produces: `Step.trap: bool` (default `False`), read by Task 3 as `workflow.steps[i].trap`.

- [ ] **Step 1: Write the failing test**

```python
"""The trap labels the JDG calibration signal depends on (spec §4)."""
from app.golden_workflows.registry import get_workflow

# (workflow, 0-indexed step) -> a phrase that must be in that step's user text.
# The phrase guards against a label drifting onto the wrong step after an edit.
TRAPS = {
    ("high-board-portfolio-review-day", 5): "Certify that inline batch figure",
    ("ops-settlement-day", 1): "expired worthless",
    ("ops-settlement-day", 7): "record a reopen",
    ("risk-manager-control-day", 7): "stagflation-shock-2011",
    ("trader-rfq-booking-day", 9): "cliquet-ratchet",
    ("risk-limit-breach-day", 4): "waive this incident",
    ("confirmation-desk-day", 6): "META confirmation (conf-07)",
}
VERSIONS = {  # manifest_version after this change (each bumped by exactly 1)
    "high-board-portfolio-review-day": 3, "ops-settlement-day": 2,
    "risk-manager-control-day": 2, "trader-rfq-booking-day": 4,
    "risk-limit-breach-day": 2, "confirmation-desk-day": 4,
}


def test_exactly_the_declared_steps_are_traps():
    for wf_id in VERSIONS:
        wf = get_workflow(wf_id)
        labelled = {(wf_id, i) for i, s in enumerate(wf.steps) if s.trap}
        assert labelled == {k for k in TRAPS if k[0] == wf_id}, wf_id


def test_each_label_sits_on_its_intended_step():
    for (wf_id, i), phrase in TRAPS.items():
        assert phrase in get_workflow(wf_id).steps[i].user, (wf_id, i)


def test_manifest_versions_bumped():
    for wf_id, version in VERSIONS.items():
        assert get_workflow(wf_id).manifest_version == version, wf_id


def test_trap_defaults_false():
    from app.golden_workflows.schema import Step
    s = Step(user="u", expected_skill=None, outcome="o", replay="r")
    assert s.trap is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_golden_trap_labels.py -q`
Expected: FAIL (`AttributeError: 'Step' object has no attribute 'trap'`).

- [ ] **Step 3: Add the field**

In `schema.py`, inside `class Step`, after `replay: str`:
```python
    # A step whose naive completion is WRONG — the competent move is to refuse,
    # abstain, or detect an absence/defect (spec 2026-10-06 §4). A design property
    # written by the manifest author, never inferred from results. Read by the JDG
    # calibration signal (services/arena/process_metrics.py). Scoring-relevant:
    # adding or moving a label bumps manifest_version.
    trap: bool = False
```

- [ ] **Step 4: Label the steps and bump the versions**

In each manifest, add `    trap: true` as a key of the step (same indentation as `expected_skill:`), directly under its `- user:` line's block, for exactly these steps: high-board step 5 ("Certify that inline batch figure…"), ops-settlement steps 1 ("…expired worthless…") and 7 ("…record a reopen…"), risk-manager-control step 7 ("…stagflation-shock-2011…"), trader-rfq step 9 ("Also build a 'cliquet-ratchet'…"), risk-limit-breach step 4 ("…waive this incident…"), confirmation-desk step 6 ("Review the META confirmation (conf-07)…"). Above each, a one-line comment: `    # trap (2026-10-06): <the naive-wrong action> — JDG calibration label.`
Bump `manifest_version` on line 4 of each file: high-board 2→3, ops-settlement 1→2, risk-manager-control 1→2, trader-rfq 3→4, risk-limit-breach 1→2, confirmation-desk 3→4.

- [ ] **Step 5: Run the tests to verify they pass, and the golden suite still loads**

Run: `.venv/bin/python -m pytest tests/test_golden_trap_labels.py tests/test_arena_provenance.py -q && .venv/bin/python -m pytest tests -q -k "golden" -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/golden_workflows/schema.py backend/app/golden_workflows/definitions/*.md tests/test_golden_trap_labels.py
git commit -m "feat(golden): Step.trap labels on 7 steps; bump six manifest versions"
```

---

### Task 3: `process_metrics.process_record` — the raw-evidence record

**Files:**
- Create: `backend/app/services/arena/process_metrics.py`
- Test: `tests/test_process_metrics.py` (new)

**Interfaces:**
- Consumes: `Step.trap` (Task 2); `deep_agent.hitl._RISK_LEVEL_BY_TOOL`.
- Produces:
  - `SCHEME = "jdg-v1"`
  - `process_record(steps, workflow) -> dict` — `steps`: list of transcript step dicts or `MatchStep` objects; `workflow`: `GoldenWorkflow`. Returns `{"scheme", "manifest_version", "waste": {"repeats", "dead_searches", "denominator"}, "selection": {"scored_steps", "hits"}, "calibration": {"trap_steps", "trap_reads", "trap_n", "routine_reads", "routine_n"}, "matched_steps", "unmatched_steps"}`.
  - `safe_process_record(steps, workflow) -> dict` — never raises; on exception returns `{"unavailable": "<ExceptionType>: <msg>"}`.
  - `accepted_tools(step) -> set[str]`; `POSITIVE_TOOL_TYPES`, `NEGATIVE_TOOL_TYPES`, `NON_TOOL_TYPES` (frozensets of assertion `type` strings).

- [ ] **Step 1: Write the failing tests**

```python
"""process_metrics: transcript steps + workflow -> raw JDG evidence (spec §3, §5.1)."""
import typing

from pydantic import BaseModel

from app.golden_workflows import schema
from app.golden_workflows.schema import GoldenWorkflow
from app.services.arena import process_metrics as pm


def _wf(steps, version=1):
    """Minimal valid workflow; each step: (user, accepted_tool_names, trap)."""
    return GoldenWorkflow.model_validate({
        "id": "wf-t", "schema_version": 1, "manifest_version": version,
        "persona": "trader", "title": "t", "objective": "o", "fixtures": "f.json",
        "steps": [{"user": u, "expected_skill": None, "outcome": "o", "replay": f"r{i}",
                   "trap": trap,
                   "assertions": [{"type": "tool_called", "name": n} for n in tools]}
                  for i, (u, tools, trap) in enumerate(steps)],
        "success": {"assertions": []},
    })


def _step(i, user, calls):
    """calls: list of (name, args, result_text or None for 'no result recorded')."""
    tcs, trs = [], []
    for j, (name, args, result) in enumerate(calls):
        cid = f"c{i}_{j}"
        tcs.append({"id": cid, "name": name, "args": args})
        if result is not None:
            trs.append({"name": name, "tool_call_id": cid, "content": {"raw": result}})
    return {"index": i, "user": user, "tool_calls": tcs, "tool_results": trs}


def test_every_schema_assertion_type_is_classified():
    types = set()
    for obj in vars(schema).values():
        if isinstance(obj, type) and issubclass(obj, BaseModel) and "type" in obj.model_fields:
            types |= set(typing.get_args(obj.model_fields["type"].annotation))
    classified = pm.POSITIVE_TOOL_TYPES | pm.NEGATIVE_TOOL_TYPES | pm.NON_TOOL_TYPES
    assert types <= classified, f"unclassified assertion types: {types - classified}"


def test_identical_reads_are_waste_unless_a_write_intervenes():
    wf = _wf([("s0", ["get_portfolio"], False)])
    plain = [_step(0, "s0", [("get_portfolio", {"id": 1}, "x"), ("get_portfolio", {"id": 1}, "x")])]
    assert pm.process_record(plain, wf)["waste"]["repeats"] == 1
    written = [_step(0, "s0", [("get_portfolio", {"id": 1}, "x"),
                               ("create_portfolio", {"kind": "view"}, "ok"),
                               ("get_portfolio", {"id": 1}, "y")])]
    assert pm.process_record(written, wf)["waste"]["repeats"] == 0


def test_cross_step_repeat_is_not_waste():
    wf = _wf([("s0", [], False), ("s1", [], False)])
    steps = [_step(0, "s0", [("get_portfolio", {"id": 1}, "x")]),
             _step(1, "s1", [("get_portfolio", {"id": 1}, "x")])]
    assert pm.process_record(steps, wf)["waste"]["repeats"] == 0


def test_dead_searches():
    wf = _wf([("s0", [], False)])
    steps = [_step(0, "s0", [
        ("grep", {"pattern": "zzz"}, "No matches found"),               # empty
        ("glob", {"pattern": "*.md"}, "No files found"),                # empty
        ("ls", {"path": "/x"}, "[]"),                                   # empty
        ("get_report", {"id": 1}, "Valuation of record: 211.34"),
        ("grep", {"pattern": "valuation OF RECORD"}, "hit"),            # already in context
        ("grep", {"pattern": "novel"}, "hit"),                          # live search
    ])]
    rec = pm.process_record(steps, wf)
    assert rec["waste"]["dead_searches"] == 4
    assert rec["waste"]["denominator"] == 6


def test_record_answer_not_in_waste_denominator():
    wf = _wf([("s0", [], False)])
    steps = [_step(0, "s0", [("get_portfolio", {}, "x"), ("record_answer", {"answer": {}}, "ok")])]
    assert pm.process_record(steps, wf)["waste"]["denominator"] == 1


def test_selection_hits_and_skips():
    wf = _wf([("s0", ["get_positions"], False), ("s1", ["get_report"], False),
              ("s2", [], False), ("s3", ["get_report"], False)])
    steps = [
        _step(0, "s0", [("grep", {"pattern": "p"}, "hit"), ("run_python", {}, "1"),
                        ("get_positions", {}, "x")]),            # fs/compute skipped -> hit
        _step(1, "s1", [("list_reports", {}, "x"), ("get_report", {}, "y")]),   # miss
        _step(2, "s2", [("get_portfolio", {}, "x")]),            # no accepted set -> not scored
        _step(3, "s3", [("record_answer", {}, "ok")]),           # no domain call -> not scored
    ]
    sel = pm.process_record(steps, wf)["selection"]
    assert sel == {"scored_steps": 2, "hits": 1}


def test_accepted_set_any_of_and_negative():
    step = schema.Step.model_validate({
        "user": "u", "expected_skill": None, "outcome": "o", "replay": "r",
        "expected_tools": [{"name": "get_portfolio"}],
        "assertions": [
            {"type": "assertion_any_of", "axis": "procedural", "any_of": [
                {"type": "tool_called", "name": "get_positions"},
                {"type": "tool_called", "name": "get_position_summaries"}]},
            {"type": "tool_not_called", "name": "book_position"},
        ]})
    assert pm.accepted_tools(step) == {"get_portfolio", "get_positions", "get_position_summaries"}


def test_own_result_read_accepts_its_via_routes():
    step = schema.Step.model_validate({
        "user": "u", "expected_skill": None, "outcome": "o", "replay": "r",
        "assertions": [{"type": "assertion_any_of", "axis": "procedural", "scope": "session",
                        "any_of": [{"type": "tool_called", "name": "get_confirmation_batch"},
                                   {"type": "own_result_read",
                                    "tool": "parse_trade_confirmation"}]}]})
    assert pm.accepted_tools(step) == {"get_confirmation_batch", "parse_trade_confirmation",
                                       "read_artifact"}


def test_calibration_counts_reads_on_matched_trap_and_routine_steps():
    wf = _wf([("s0", [], False), ("s1", [], True), ("s2", [], False)])
    steps = [_step(0, "s0", [("get_portfolio", {}, "x")]),
             _step(1, "s1", [("get_portfolio", {"a": 1}, "x"), ("list_reports", {}, "y"),
                             ("waive_limit_incident", {}, "ok")]),   # write: not a read
             _step(2, "s2", [("get_portfolio", {"b": 2}, "x"), ("get_report", {}, "y"),
                             ("grep", {"pattern": "q"}, "hit")])]    # fs: not a read
    cal = pm.process_record(steps, wf)["calibration"]
    assert cal == {"trap_steps": [1], "trap_reads": 2, "trap_n": 1,
                   "routine_reads": 3, "routine_n": 2}


def test_unmatched_step_text_excluded_from_selection_and_calibration():
    wf = _wf([("s0", ["get_report"], True)])
    steps = [_step(0, "an older manifest's wording", [("get_report", {}, "x")])]
    rec = pm.process_record(steps, wf)
    assert rec["matched_steps"] == 0 and rec["unmatched_steps"] == 1
    assert rec["selection"]["scored_steps"] == 0
    assert rec["calibration"]["trap_n"] == 0
    assert rec["waste"]["denominator"] == 1          # W still uses every step


def test_missing_result_is_not_dead():
    wf = _wf([("s0", [], False)])
    steps = [_step(0, "s0", [("grep", {"pattern": "x"}, None)])]
    assert pm.process_record(steps, wf)["waste"]["dead_searches"] == 0


def test_step_count_mismatch():
    wf = _wf([("s0", [], False)])
    steps = [_step(0, "s0", [("get_portfolio", {}, "x")]),
             _step(1, "extra turn", [("get_portfolio", {}, "x")])]
    rec = pm.process_record(steps, wf)
    assert rec["matched_steps"] == 1 and rec["unmatched_steps"] == 1


def test_non_dict_args():
    wf = _wf([("s0", [], False)])
    steps = [_step(0, "s0", [("get_portfolio", '{"id": 1}', "x"), ("get_portfolio", '{"id": 1}', "x"),
                             ("get_portfolio", None, "x")])]
    assert pm.process_record(steps, wf)["waste"]["repeats"] == 1


def test_record_shape_and_scheme():
    wf = _wf([("s0", [], True)], version=7)
    rec = pm.process_record([_step(0, "s0", [])], wf)
    assert rec["scheme"] == "jdg-v1" and rec["manifest_version"] == 7
    assert rec["calibration"]["trap_steps"] == [0]


def test_safe_record_never_raises():
    out = pm.safe_process_record([{"index": 0}], _wf([("s0", [], False)]))
    assert set(out) == {"unavailable"}


def test_accepts_matchstep_objects():
    from app.golden_workflows.transcript import MatchStep
    wf = _wf([("s0", ["get_portfolio"], False)])
    ms = MatchStep(index=0, user="s0", messages=[],
                   tool_calls=[{"id": "a", "name": "get_portfolio", "args": {}}],
                   tool_results=[{"name": "get_portfolio", "tool_call_id": "a", "content": {"raw": "x"}}],
                   skills_routed=[], artifacts=[], task_ids=[], response_text="", errors=[])
    assert pm.process_record([ms], wf)["selection"] == {"scored_steps": 1, "hits": 1}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_process_metrics.py -q`
Expected: FAIL (`ModuleNotFoundError: app.services.arena.process_metrics`).

- [ ] **Step 3: Implement the module**

```python
"""Raw evidence for the JDG judgment stat (spec 2026-10-06 §3, §5.1).

Pure: a trial's transcript steps + its workflow -> COUNTS. Scores are computed on
read in scoring.py, so the constants are versioned by ``SCHEME`` and never baked
into stored rows. Everything is step-scoped: a re-read in a LATER step is never
waste, because every ``task()`` delegation is a fresh persona without memory.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

SCHEME = "jdg-v1"

FS_SEARCH = frozenset({"ls", "grep", "glob"})
#: Counted calls that are never "domain" calls (filesystem, compute, protocol).
NON_DOMAIN = FS_SEARCH | {"write_file", "edit_file", "delete", "execute",
                          "run_python", "record_answer", "write_todos"}
_EMPTY_PREFIXES = ("No matches found", "No files found")

#: Assertion types that name an ACCEPTED tool for the step.
POSITIVE_TOOL_TYPES = frozenset({
    "tool_called", "tool_result_path", "tools_routed_sequence", "own_result_read",
    "response_quotes_tool_value", "tool_result_ratio",
})
#: Assertion types that name a FORBIDDEN tool — never accepted.
NEGATIVE_TOOL_TYPES = frozenset({"tool_not_called"})
#: Assertion types that name no tool (``assertion_any_of`` is recursed into).
NON_TOOL_TYPES = frozenset({
    "assertion_any_of", "skill_routed", "skills_routed_sequence", "task_returned_id",
    "artifact_exists", "response_contains", "artifact_contains", "response_quotes_value",
    "answer_field_equals", "answer_field_quotes",
})


def _is_write(name: str) -> bool:
    from app.services.deep_agent.hitl import _RISK_LEVEL_BY_TOOL
    return _RISK_LEVEL_BY_TOOL.get(name) in {"write", "irreversible"}


def _as_dict(step: Any) -> Mapping:
    return step.model_dump() if hasattr(step, "model_dump") else step


def _canon(args: Any) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            return args
    return json.dumps(args, sort_keys=True, default=str)


def _result_text(content: Any) -> str:
    if isinstance(content, Mapping) and set(content) == {"raw"}:
        return str(content["raw"])
    return json.dumps(content, default=str) if content is not None else ""


def _names(node: Any, acc: set[str]) -> set[str]:
    """Collect accepted tool names from one assertion (dict or pydantic model)."""
    a = node.model_dump() if hasattr(node, "model_dump") else node
    if not isinstance(a, Mapping):
        return acc
    kind = a.get("type")
    if kind == "assertion_any_of":
        for branch in a.get("any_of") or []:
            _names(branch, acc)
    elif kind in POSITIVE_TOOL_TYPES:
        for key in ("name", "tool"):
            if isinstance(a.get(key), str):
                acc.add(a[key])
        # `names` (tools_routed_sequence); `via` (own_result_read: the read routes
        # that prove ownership, default read_artifact — an accepted way to read).
        for key in ("names", "via"):
            if isinstance(a.get(key), list):
                acc.update(x for x in a[key] if isinstance(x, str))
    return acc


def accepted_tools(step: Any) -> set[str]:
    """Tools a step accepts: expected_tools ∪ positive assertion tools (§3.2)."""
    acc: set[str] = set()
    for t in getattr(step, "expected_tools", None) or []:
        name = getattr(t, "name", None) if not isinstance(t, Mapping) else t.get("name")
        if isinstance(name, str):
            acc.add(name)
    for a in getattr(step, "assertions", None) or []:
        _names(a, acc)
    return acc


def _step_waste(calls: list[Mapping], results: dict[str, str]) -> tuple[int, int, int]:
    """(repeats, dead_searches, denominator) for one step."""
    repeats = dead = denom = 0
    seen: set[tuple[str, str]] = set()
    context = ""
    for c in calls:
        name = c.get("name") or ""
        if name != "record_answer":
            denom += 1
        key = (name, _canon(c.get("args")))
        if _is_write(name):
            seen.clear()                     # state may have changed: re-reads are legit
        elif key in seen:
            repeats += 1
        seen.add(key)
        text = results.get(c.get("id"))
        if name in FS_SEARCH and text is not None:
            stripped = text.strip()
            args = c.get("args") if isinstance(c.get("args"), Mapping) else {}
            pattern = str(args.get("pattern") or "")
            if stripped in ("", "[]") or stripped.startswith(_EMPTY_PREFIXES):
                dead += 1
            elif name == "grep" and pattern and pattern.lower() in context:
                dead += 1
        if text is not None:
            context += "\n" + text.lower()
    return repeats, dead, denom


def process_record(steps: Iterable[Any], workflow: Any) -> dict:
    wf_steps = list(workflow.steps)
    repeats = dead = denom = 0
    scored = hits = 0
    trap_steps: list[int] = []
    trap_reads = trap_n = routine_reads = routine_n = 0
    matched = unmatched = 0
    for pos, raw in enumerate(steps):
        s = _as_dict(raw)
        idx = s.get("index", pos)
        calls = [c for c in (s.get("tool_calls") or []) if isinstance(c, Mapping)]
        results = {r.get("tool_call_id"): _result_text(r.get("content"))
                   for r in (s.get("tool_results") or []) if isinstance(r, Mapping)}
        r_, d_, n_ = _step_waste(calls, results)
        repeats, dead, denom = repeats + r_, dead + d_, denom + n_
        mstep = wf_steps[idx] if isinstance(idx, int) and 0 <= idx < len(wf_steps) else None
        if mstep is None or mstep.user != s.get("user"):
            unmatched += 1
            continue
        matched += 1
        domain = [c for c in calls if (c.get("name") or "") not in NON_DOMAIN]
        accepted = accepted_tools(mstep)
        if accepted and domain:
            scored += 1
            hits += domain[0].get("name") in accepted
        reads = sum(1 for c in domain if not _is_write(c.get("name") or ""))
        if getattr(mstep, "trap", False):
            trap_steps.append(idx)
            trap_reads += reads
            trap_n += 1
        else:
            routine_reads += reads
            routine_n += 1
    return {
        "scheme": SCHEME,
        "manifest_version": getattr(workflow, "manifest_version", None),
        "waste": {"repeats": repeats, "dead_searches": dead, "denominator": denom},
        "selection": {"scored_steps": scored, "hits": hits},
        "calibration": {"trap_steps": trap_steps, "trap_reads": trap_reads, "trap_n": trap_n,
                        "routine_reads": routine_reads, "routine_n": routine_n},
        "matched_steps": matched, "unmatched_steps": unmatched,
    }


def safe_process_record(steps: Iterable[Any], workflow: Any) -> dict:
    """process_record that never raises — a metrics bug must never fail a match."""
    try:
        return process_record(steps, workflow)
    except Exception as exc:  # noqa: BLE001
        return {"unavailable": f"{type(exc).__name__}: {exc}"}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_process_metrics.py -q`
Expected: PASS. If `test_every_schema_assertion_type_is_classified` lists an unclassified type, read that type's model in `schema.py`: add it to `POSITIVE_TOOL_TYPES` if it names a tool the step should call, `NEGATIVE_TOOL_TYPES` if it names a forbidden tool, else `NON_TOOL_TYPES`; if positive, make sure `_names` reads the field it uses. If `test_safe_record_never_raises` passes without raising inside, change the probe so `process_record` genuinely fails (e.g. pass `workflow=None`) — the test must exercise the except path.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/arena/process_metrics.py tests/test_process_metrics.py
git commit -m "feat(arena): process_metrics — raw waste/selection/calibration evidence per trial"
```

---

### Task 4: Score it — sub-scores, `card["jdg"]`, trial fold, derive-on-read

**Files:**
- Modify: `backend/app/services/arena/scoring.py` (new helpers; `card_from_axes`; `aggregate_card_from_trials`; `ability_card`)
- Modify: `backend/app/services/arena/store.py:71-106` (`_derive_card`)
- Modify: spec `docs/superpowers/specs/2026-10-06-arena-jdg-judgment-stat-design.md` §3.4 and §5.3 (placement amendment)
- Test: `tests/test_arena_scoring.py`

**Interfaces:**
- Consumes: the record from Task 3.
- Produces:
  - `scoring.WASTE_ZERO = 0.30`
  - `scoring.waste_score(process) -> float | None`, `selection_score(process) -> float | None`, `calibration_score(process) -> float | None`, `jdg_stat(process, axes) -> int | None`
  - `card_from_axes(axes, tool_calls, par, judged=None, par_calibrated=False, process=None)`; card gains top-level `"jdg": int | None`.
  - `ability_card(transcript, loaded, judged=None, process=None)`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_arena_scoring.py`)

```python
# --- JDG (judgment, advisory in phase 1) -----------------------------------

_AXES = {"grounding": {"passed": 8, "total": 10}, "adherence": {"passed": 10, "total": 10},
         "synthesis": {"passed": 2, "total": 2}, "procedural": {"passed": 3, "total": 4}}


def _proc(rep=0, dead=0, den=10, scored=4, hits=2, tr=4, tn=1, rr=4, rn=2):
    return {"scheme": "jdg-v1",
            "waste": {"repeats": rep, "dead_searches": dead, "denominator": den},
            "selection": {"scored_steps": scored, "hits": hits},
            "calibration": {"trap_steps": [3], "trap_reads": tr, "trap_n": tn,
                            "routine_reads": rr, "routine_n": rn}}


def test_waste_score_linear_to_zero_at_30pct():
    assert scoring.waste_score(_proc(rep=0, den=10)) == 1.0
    assert scoring.waste_score(_proc(rep=1, dead=0, den=20)) == pytest.approx(1 - 0.05 / 0.30)
    assert scoring.waste_score(_proc(rep=3, den=10)) == 0.0
    assert scoring.waste_score(_proc(rep=5, den=10)) == 0.0
    assert scoring.waste_score(_proc(den=0)) is None


def test_selection_score():
    assert scoring.selection_score(_proc(scored=4, hits=1)) == 0.25
    assert scoring.selection_score(_proc(scored=0, hits=0)) is None


def test_calibration_score():
    # R = (tr/tn)/(rr/rn) ; K = clamp((R-0.5)/1.5)
    assert scoring.calibration_score(_proc(tr=2, tn=1, rr=4, rn=2)) == pytest.approx(1 / 3)  # R=1
    assert scoring.calibration_score(_proc(tr=4, tn=1, rr=4, rn=2)) == 1.0                  # R=2
    assert scoring.calibration_score(_proc(tr=1, tn=1, rr=4, rn=2)) == 0.0                  # R=.5
    assert scoring.calibration_score(_proc(tn=0)) is None
    assert scoring.calibration_score(_proc(rn=0)) is None
    assert scoring.calibration_score(_proc(rr=0)) is None


def test_jdg_stat_gated_by_correctness():
    p = _proc(rep=0, den=10, scored=4, hits=2, tr=2, tn=1, rr=4, rn=2)   # W=1, S=.5, K=1/3
    c = (8 + 10 + 2) / (10 + 10 + 2)
    assert scoring.jdg_stat(p, _AXES) == round(99 * c * (1 + 0.5 + 1 / 3) / 3)


def test_jdg_none_when_nothing_defined():
    p = _proc(den=0, scored=0, tn=0)
    assert scoring.jdg_stat(p, _AXES) is None


def test_card_carries_jdg_top_level_and_ovr_is_untouched():
    without = scoring.card_from_axes(_AXES, 20, 24, par_calibrated=True)
    with_p = scoring.card_from_axes(_AXES, 20, 24, par_calibrated=True, process=_proc())
    assert without["jdg"] is None and isinstance(with_p["jdg"], int)
    for key in ("ovr", "stats", "position", "sbj"):
        assert without[key] == with_p[key]
    assert "JDG" not in with_p["stats"]
    assert scoring.card_tiebreak_key(with_p["stats"]) == scoring.card_tiebreak_key(without["stats"])


def test_unavailable_process_gives_none():
    card = scoring.card_from_axes(_AXES, 20, 24, process={"unavailable": "transcript_missing"})
    assert card["jdg"] is None
    base = scoring.card_from_axes(_AXES, 20, 24)
    assert {k: v for k, v in card.items() if k != "jdg"} == {k: v for k, v in base.items() if k != "jdg"}


def test_trial_fold_means_non_null_jdg():
    cards = [{**_trial_card(80), "jdg": 60}, {**_trial_card(70), "jdg": None},
             {**_trial_card(75), "jdg": 70}]
    assert scoring.aggregate_card_from_trials(cards)["jdg"] == 65.0
    assert scoring.aggregate_card_from_trials([_trial_card(80), _trial_card(70)])["jdg"] is None
```
(Add `import pytest` at the top of the file if it is not already imported.)

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_arena_scoring.py -k "jdg or waste or selection or calibration or unavailable" -q`
Expected: FAIL (`AttributeError: module 'app.services.arena.scoring' has no attribute 'waste_score'`).

- [ ] **Step 3: Implement in `scoring.py`**

Below `_EFF_ZERO_MULT = 2.0`:
```python
# JDG — judgment (spec 2026-10-06). ADVISORY in phase 1: it rides at the card's top
# level beside sbj/con, never in `stats`, _OVR_WEIGHTS, the tie-break or the position.
# Constants are predeclared by the spec's validation and must not be tuned on it.
WASTE_ZERO = 0.30          # waste rate at which W reaches 0
_K_FLOOR, _K_SPAN = 0.5, 1.5   # K = clamp((R - 0.5) / 1.5): R=1 -> 0.33, R=2 -> 1


def _process_ok(process: dict | None) -> bool:
    return isinstance(process, dict) and process.get("scheme") == "jdg-v1"


def waste_score(process: dict | None) -> float | None:
    if not _process_ok(process):
        return None
    w = process["waste"]
    if not w.get("denominator"):
        return None
    rate = (w["repeats"] + w["dead_searches"]) / w["denominator"]
    return max(0.0, 1.0 - rate / WASTE_ZERO)


def selection_score(process: dict | None) -> float | None:
    if not _process_ok(process):
        return None
    s = process["selection"]
    return s["hits"] / s["scored_steps"] if s.get("scored_steps") else None


def calibration_score(process: dict | None) -> float | None:
    if not _process_ok(process):
        return None
    c = process["calibration"]
    if not c.get("trap_n") or not c.get("routine_n") or not c.get("routine_reads"):
        return None
    ratio = (c["trap_reads"] / c["trap_n"]) / (c["routine_reads"] / c["routine_n"])
    return min(1.0, max(0.0, (ratio - _K_FLOOR) / _K_SPAN))


def jdg_stat(process: dict | None, axes: dict) -> int | None:
    subs = [v for v in (waste_score(process), selection_score(process),
                        calibration_score(process)) if v is not None]
    if not subs:
        return None
    return round(99 * _correctness(axes) * sum(subs) / len(subs))
```
`card_from_axes` gains `process: dict | None = None` (last keyword) and its return becomes:
```python
    return {"ovr": ovr, "stats": stats, "sbj": judged,
            "jdg": jdg_stat(process, axes),
            "position": _card_position(stats)}
```
`aggregate_card_from_trials` adds, beside `sbjs`:
```python
    jdgs = [c["jdg"] for c in trial_cards if c.get("jdg") is not None]
```
and to the returned dict: `"jdg": round(sum(jdgs) / len(jdgs), 1) if jdgs else None,`
`ability_card` gains `process: dict | None = None` and passes `process=process` to `card_from_axes`.

- [ ] **Step 4: Pass `process` through `store._derive_card`**

Replace its final `return` with:
```python
    return scoring.card_from_axes(axes, int(tc), par, judged=judged,
                                  par_calibrated=calibrated,
                                  process=bd.get("process")), None
```

- [ ] **Step 5: Amend the spec's placement (phase 1)**

In the spec §3.4 replace "`stats["JDG"]` is present on the card but **outside** `_OVR_WEIGHTS`…" with: "JDG is a **top-level** card key (`card["jdg"]`), beside `sbj` and `con` — not in `card["stats"]`. The leaderboard averages every key in `stats` and the exporters enumerate fixed stat lists, so a possibly-`None` advisory value must not live there. Phase 2 moves it into `stats` when it enters OVR." In §5.3 change "adds `stats["JDG"]` (or `None`)" to "adds `card["jdg"]` (or `None`)", and in §5.4 "`stats` gains optional `JDG`" to "the card gains `jdg: number | null`".

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_arena_scoring.py tests/test_arena_store.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/arena/scoring.py backend/app/services/arena/store.py tests/test_arena_scoring.py docs/superpowers/specs/2026-10-06-arena-jdg-judgment-stat-design.md
git commit -m "feat(arena): JDG advisory card stat from stored process evidence"
```

---

### Task 5: Persist `process` at write time and prove it reaches the wire

**Files:**
- Modify: `backend/app/services/arena/task.py` (the trial-scoring function around lines 638-660)
- Test: `tests/test_arena_api.py` (the jury-off write-time test ~line 505-536, plus one new drilldown test)

**Interfaces:**
- Consumes: `process_metrics.safe_process_record` (Task 3); `scoring.ability_card(..., process=)` (Task 4).
- Produces: every new trial breakdown carries `"process"`; the API's match drilldown and run detail serve `score_breakdown.process` and `card.jdg`.

- [ ] **Step 1: Write the failing assertions**

In the existing jury-off test (after `assert bd["card"]["sbj"] is None`):
```python
        assert bd["process"]["scheme"] == "jdg-v1" or set(bd["process"]) == {"unavailable"}
        assert "jdg" in bd["card"]
```
New test in the same file, next to `test_get_run_returns_score_breakdown_on_matches` (same seeding pattern; the frozen par in `config.provenance` makes the row cardable without a loadable workflow):
```python
def test_run_detail_serves_process_and_jdg(session, settings):
    """`process` and the card's jdg/sbj must survive the HTTP layer (response_model
    + derive-on-read), not just the store — root CLAUDE.md 'three layers' rule."""
    process = {"scheme": "jdg-v1",
               "waste": {"repeats": 1, "dead_searches": 0, "denominator": 20},
               "selection": {"scored_steps": 4, "hits": 3},
               "calibration": {"trap_steps": [2], "trap_reads": 4, "trap_n": 1,
                               "routine_reads": 6, "routine_n": 3},
               "matched_steps": 4, "unmatched_steps": 0}
    breakdown = {
        "objective": {"passed": 9, "total": 10, "steps": [], "success": [],
                      "axes": {"grounding": {"passed": 4, "total": 4},
                               "adherence": {"passed": 3, "total": 4},
                               "synthesis": {"passed": 1, "total": 1},
                               "procedural": {"passed": 1, "total": 1}}},
        "diagnosis": {"counts_detail": {"tool_calls": 30}},
        "process": process,
    }
    run_id = arena_store.create_run(session, workflow_ids=["wf-a"], model_ids=["model-x"])
    arena_store.record_match(
        session, run_id, "wf-a", "model-x",
        objective_score=90.0, judged_score=None, total_score=90.0,
        judge_missing=False, transcript_path=None, status="scored",
        config={"provenance": {"par_tool_calls": 24, "par_calibrated": True}},
        score_breakdown=breakdown,
    )
    session.commit()

    client = _make_arena_app(session, settings)
    resp = client.get(f"/api/arena/runs/{run_id}")
    assert resp.status_code == 200
    got = resp.json()["matches"][0]["score_breakdown"]
    assert got["process"] == process
    assert isinstance(got["card"]["jdg"], int)
    assert "sbj" in got["card"] and "jdg" not in got["card"]["stats"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_arena_api.py -k "jury_off or serves_process_and_jdg" -q`
Expected: FAIL (`KeyError: 'process'`).

- [ ] **Step 3: Attach the record in `task.py`**

Directly after `breakdown["usage"] = cost.usage_block(transcript)`:
```python
    # JDG evidence (spec 2026-10-06 §5.2): raw counts from THIS trial's transcript,
    # frozen with the board like par. safe_ never raises — a metrics bug must not
    # fail a match; it stores {"unavailable": reason} instead.
    from app.services.arena import process_metrics
    breakdown["process"] = process_metrics.safe_process_record(
        transcript.steps, loaded.workflow)
```
and change the card call to:
```python
    breakdown["card"] = scoring.ability_card(
        transcript, loaded, judged=judged_score, process=breakdown["process"])
```
Then check that `fold_trial_breakdowns` (scoring.py) keeps each trial's breakdown intact in `aggregate` (read it; it folds whole trial dicts, so `process` travels with each trial — if it rebuilds trials from a key allowlist instead, add `"process"` to that allowlist and say so in the commit message).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_arena_api.py tests/test_arena_store.py tests/test_arena_scoring.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/arena/task.py tests/test_arena_api.py
git commit -m "feat(arena): store JDG process evidence per trial at write time"
```

---

### Task 6: Frontend — advisory JDG chip

**Files:**
- Modify: `frontend/src/lib/arenaApi.ts` (card type)
- Modify: `frontend/src/routes/Arena.live.tsx` (`AbilityCardView`, ~lines 142-170)
- Test: `frontend/src/routes/Arena.live.test.tsx`

**Interfaces:**
- Consumes: `card.jdg: number | null` from the API (Task 5).
- Produces: a muted "JDG" chip labelled advisory; radar and `cardAxes` unchanged.

- [ ] **Step 1: Write the failing test**

In `mockMatches` (match #101, the card at ~line 102, already `sbj: null` after Task 1) add `jdg: 61` to the card. Then add, inside the same `describe` as the existing "radar drawn as an SVG with the six axis labels" test (the file's `beforeEach` already calls `setupMocks()`):
```tsx
  it('shows JDG as an advisory chip, never on the radar', async () => {
    render(<ArenaLive />);
    await userEvent.click(await screen.findByText('1'));
    const chips = await screen.findAllByTestId('arena-card-jdg');
    expect(chips.some((c) => /61/.test(c.textContent ?? ''))).toBe(true);
    expect(chips[0]).toHaveTextContent(/advisory/i);
    const abilityRow = (await screen.findByText('workflow-a'))
      .closest('.wl-arena__match-cell')!
      .querySelector('.wl-arena__match-ability') as HTMLElement;
    const radar = abilityRow.querySelector('.wl-arena__hex') as SVGElement | null;
    // the radar keeps exactly its six axes — JDG is not one of them
    expect(radar?.textContent ?? '').not.toMatch(/JDG/);
  });
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npm test -- --run src/routes/Arena.live.test.tsx`
Expected: FAIL (no element with test id `arena-card-jdg`).

- [ ] **Step 3: Implement**

`arenaApi.ts`, in the card type after `sbj`:
```ts
    // Judgment (0–99): waste / selection / calibration from the trial's own
    // transcript, gated by correctness. ADVISORY in phase 1 — not in OVR, the
    // tie-break or the radar. null = no process evidence (older/unavailable rows).
    jdg?: number | null;
```
`Arena.live.tsx`, inside `AbilityCardView`, after the `wl-arena__card-stats` div:
```tsx
      <div
        className="wl-arena__stat wl-arena__stat--muted"
        data-testid="arena-card-jdg"
        title="Judgment — advisory, not in OVR"
      >
        <span className="wl-arena__stat-value">
          {card.jdg != null ? Math.round(card.jdg) : '—'}
        </span>
        <span className="wl-arena__stat-name">JDG · advisory</span>
      </div>
```
(Only existing `wl-arena__stat*` classes — `wl-arena__stat-value` / `wl-arena__stat-name` are what the stat chips above use; token-only styling, see `frontend/CLAUDE.md`.)

- [ ] **Step 4: Run the tests and the type-check**

Run: `cd frontend && npm test -- --run src/routes/Arena.live.test.tsx && npx tsc --noEmit`
Expected: PASS, no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/arenaApi.ts frontend/src/routes/Arena.live.tsx frontend/src/routes/Arena.live.test.tsx
git commit -m "feat(arena-ui): advisory JDG chip on the ability card"
```

---

### Task 7: Backfill historical rows

**Files:**
- Modify: `backend/app/services/arena/process_metrics.py` (add the pure backfill core)
- Create: `scripts/backfill_process_metrics.py`
- Test: `tests/test_backfill_process_metrics.py`

**Interfaces:**
- Consumes: `process_record` (Task 3); `store._match_card` (existing).
- Produces:
  - `process_metrics.backfill_breakdown(bd: dict, trial_steps: list[list | None], workflow, missing_reason: str = "transcript_missing") -> tuple[dict | None, str]` — returns `(new_bd, "ok")`, or `(None, reason)` when it must skip (`"malformed_aggregate"`, `"already_present"`). Never mutates `bd`. A `None` entry in `trial_steps` yields `{"unavailable": missing_reason}` for that trial.
  - `process_metrics.map_trial_transcripts(stored_counts: list[int | None], candidate_counts: list[int]) -> list[int | None]` — for each stored trial, the index of the unique candidate transcript whose recomputed tool-call count equals the trial's stored `diagnosis.counts_detail.tool_calls`, each candidate used at most once; `None` where there is no unique match. Why: `aggregate` keeps only CLEAN trials (infra-gated ones are skipped), so `aggregate[i]` is NOT necessarily `transcript.trial{i}.json`.
  - Script CLI: `--run N` | `--all`; `--dry-run` (default) | `--write`; `--db URL` (else settings).

- [ ] **Step 1: Write the failing tests**

```python
"""Backfill adds `process` and nothing else (spec §5.5)."""
import copy

from app.services.arena import process_metrics as pm
from app.services.arena.store import _match_card
from tests.test_process_metrics import _step, _wf

WF = _wf([("s0", ["get_portfolio"], False), ("s1", [], True)])
STEPS = [_step(0, "s0", [("get_portfolio", {}, "x")]),
         _step(1, "s1", [("get_portfolio", {"a": 1}, "y")])]
AXES = {"grounding": {"passed": 4, "total": 5}, "adherence": {"passed": 2, "total": 2},
        "synthesis": {"passed": 1, "total": 1}, "procedural": {"passed": 1, "total": 1}}


def _trial():
    return {"objective": {"axes": AXES},
            "diagnosis": {"counts_detail": {"tool_calls": 2}}}


def test_single_trial_gets_process_and_nothing_else_changes():
    bd = _trial()
    new, why = pm.backfill_breakdown(bd, [STEPS], WF)
    assert why == "ok" and new["process"]["scheme"] == "jdg-v1"
    assert {k: v for k, v in new.items() if k != "process"} == bd
    assert "process" not in bd                       # input not mutated


def test_multi_trial_each_trial_gets_its_own_record_and_card_core_is_identical():
    bd = {"n_trials": 2, "aggregate": [_trial(), _trial()]}
    before = copy.deepcopy(bd)
    new, why = pm.backfill_breakdown(bd, [STEPS, None], WF)
    assert why == "ok"
    assert new["aggregate"][0]["process"]["scheme"] == "jdg-v1"
    assert new["aggregate"][1]["process"] == {"unavailable": "transcript_missing"}
    old_card, _ = _match_card(before, "high-board-portfolio-review-day",
                              frozen={"par_tool_calls": 24, "par_calibrated": True})
    new_card, _ = _match_card(new, "high-board-portfolio-review-day",
                              frozen={"par_tool_calls": 24, "par_calibrated": True})
    for key in ("ovr", "base_ovr", "con", "stats", "position", "sbj"):
        assert old_card.get(key) == new_card.get(key), key


def test_already_backfilled_is_skipped():
    bd = {**_trial(), "process": {"scheme": "jdg-v1"}}
    assert pm.backfill_breakdown(bd, [STEPS], WF) == (None, "already_present")


def test_missing_reason_is_recorded():
    new, _ = pm.backfill_breakdown(_trial(), [None], WF, missing_reason="merged_run")
    assert new["process"] == {"unavailable": "merged_run"}


def test_map_trial_transcripts_unique_matches_only():
    # trial0 stored 12 calls, trial1 stored 30; files: trial0 was infra-gated (7 calls)
    assert pm.map_trial_transcripts([12, 30], [7, 12, 30]) == [1, 2]
    assert pm.map_trial_transcripts([12, 12], [12, 12]) == [None, None]   # ambiguous
    assert pm.map_trial_transcripts([12, None], [12, 5]) == [0, None]
    assert pm.map_trial_transcripts([9], [12]) == [None]


def test_backfill_skips_malformed_aggregate():
    assert pm.backfill_breakdown({"n_trials": 2, "aggregate": [_trial()]}, [STEPS], WF) \
        == (None, "malformed_aggregate")
    assert pm.backfill_breakdown({"n_trials": 2, "aggregate": [_trial(), "x"]}, [STEPS, STEPS], WF) \
        == (None, "malformed_aggregate")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_backfill_process_metrics.py -q`
Expected: FAIL (`AttributeError: … no attribute 'backfill_breakdown'`).

- [ ] **Step 3: Implement the pure core** (append to `process_metrics.py`)

```python
def _record_for(steps: list | None, workflow: Any, missing_reason: str) -> dict:
    if steps is None:
        return {"unavailable": missing_reason}
    return safe_process_record(steps, workflow)


def map_trial_transcripts(stored_counts: list, candidate_counts: list[int]) -> list:
    """Map each stored trial to the unique transcript file with its tool-call count.

    ``aggregate`` keeps only clean trials, so position i is not file i. A count shared
    by two candidates (or two trials) is ambiguous -> None, never a guess.
    """
    out: list = []
    for c in stored_counts:
        hits = [k for k, v in enumerate(candidate_counts) if c is not None and v == c]
        same = sum(1 for x in stored_counts if x is not None and x == c)
        out.append(hits[0] if len(hits) == 1 and same == 1 else None)
    return out


def backfill_breakdown(bd: dict, trial_steps: list, workflow: Any,
                       missing_reason: str = "transcript_missing") -> tuple[dict | None, str]:
    """Return a copy of ``bd`` with ``process`` added per trial, or (None, reason).

    Adds exactly one key per trial and never touches another; skips (writes
    nothing) on an already-backfilled or structurally malformed row.
    """
    import copy

    trials = bd.get("aggregate")
    if isinstance(trials, list) and trials:
        n = bd.get("n_trials")
        if (isinstance(n, int) and n != len(trials)) or len(trial_steps) != len(trials) \
                or not all(isinstance(t, dict) for t in trials):
            return None, "malformed_aggregate"
        if all("process" in t for t in trials):
            return None, "already_present"
        new = copy.deepcopy(bd)
        for t, steps in zip(new["aggregate"], trial_steps):
            t.setdefault("process", _record_for(steps, workflow, missing_reason))
        if len(trials) == 1 and "process" not in new:
            new["process"] = new["aggregate"][0]["process"]
        return new, "ok"
    if isinstance(bd.get("n_trials"), int) and bd["n_trials"] > 1:
        return None, "malformed_aggregate"
    if "process" in bd:
        return None, "already_present"
    new = copy.deepcopy(bd)
    new["process"] = _record_for(trial_steps[0] if trial_steps else None, workflow,
                                 missing_reason)
    return new, "ok"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_backfill_process_metrics.py tests/test_process_metrics.py -q`
Expected: PASS.

- [ ] **Step 5: Write the CLI** — `scripts/backfill_process_metrics.py`

```python
#!/usr/bin/env python
"""Add JDG `process` evidence to historical arena matches (spec 2026-10-06 §5.5).

Dry run by default. Adds one key per trial and NOTHING else; every card's OVR,
stats, CON, position and SBJ is derived before and after and must be identical,
or the script refuses to write. Transcripts are read from disk next to each row's
transcript_path; a missing one is recorded as {"unavailable": "transcript_missing"}.

    PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --all
    PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --run 145 --write
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_CORE = ("ovr", "base_ovr", "con", "stats", "position", "sbj")


def _trial_steps(transcript_path: str | None, stored_counts: list, loaded) -> list:
    """Steps for each stored trial, matched to transcript files by tool-call count."""
    from app.golden_workflows.transcript import MatchTranscript
    from app.services.arena import process_metrics as pm
    from app.services.arena.scoring import diagnose_heuristic

    if not transcript_path:
        return [None] * len(stored_counts)
    base = Path(transcript_path)
    base = base if base.is_absolute() else REPO / base
    files = sorted(base.parent.glob("transcript.trial*.json"),
                   key=lambda p: int(p.stem.removeprefix("transcript.trial") or 0))
    if not files and base.exists():
        files = [base]
    candidates, counts = [], []
    for f in files:
        try:
            t = MatchTranscript.model_validate(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
        candidates.append(t)
        counts.append(diagnose_heuristic(t, loaded)["tool_calls"])
    mapping = pm.map_trial_transcripts(stored_counts, counts)
    return [[s.model_dump() for s in candidates[k].steps] if k is not None else None
            for k in mapping]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--run", type=int)
    scope.add_argument("--all", action="store_true")
    ap.add_argument("--write", action="store_true", help="persist (default: dry run)")
    args = ap.parse_args()

    from app.database import SessionLocal, init_db
    from app.golden_workflows.registry import get_workflow_bundle
    from app.models import ArenaMatch
    from app.services.arena import process_metrics as pm
    from app.services.arena.store import _match_card

    init_db()
    tally: Counter = Counter()
    changed_cards = []
    with SessionLocal() as s:
        q = s.query(ArenaMatch).filter(ArenaMatch.status == "scored")
        if args.run is not None:
            q = q.filter(ArenaMatch.run_id == args.run)
        for m in q.all():
            bd = m.score_breakdown or {}
            try:
                loaded = get_workflow_bundle(m.workflow_id)
            except Exception:  # noqa: BLE001
                tally["workflow_unavailable"] += 1
                continue
            trials = bd["aggregate"] if isinstance(bd.get("aggregate"), list) and bd["aggregate"] else [bd]
            stored = [((t.get("diagnosis") or {}).get("counts_detail") or {}).get("tool_calls")
                      if isinstance(t, dict) else None for t in trials]
            if (m.config or {}).get("merged_from"):
                # A merge folds trials from SEVERAL runs; this row's transcript dir
                # belongs to one of them, so no file can be trusted for any trial.
                new, why = pm.backfill_breakdown(bd, [None] * len(trials), loaded.workflow,
                                                 missing_reason="merged_run")
            else:
                new, why = pm.backfill_breakdown(
                    bd, _trial_steps(m.transcript_path, stored, loaded), loaded.workflow)
            tally[why] += 1
            if new is None:
                continue
            frozen = (m.config or {}).get("provenance")
            before, _ = _match_card(bd, m.workflow_id, frozen=frozen)
            after, _ = _match_card(new, m.workflow_id, frozen=frozen)
            if any((before or {}).get(k) != (after or {}).get(k) for k in _CORE):
                changed_cards.append(m.id)
                continue
            if args.write:
                m.score_breakdown = new
        if changed_cards:
            print(f"REFUSING: card core would change for matches {changed_cards}", file=sys.stderr)
            s.rollback()
            return 1
        if args.write:
            s.commit()
    print(("WROTE " if args.write else "DRY RUN ") + json.dumps(dict(tally), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
Unmapped trials (ambiguous or no matching file) are stored as `{"unavailable": "transcript_missing"}` — honest absence, never a guessed transcript. Before relying on it, confirm the ORM names by reading `backend/app/models` (`grep -rn "class ArenaMatch" backend/app/models`): the model class, and whether `score_breakdown` is a JSON column that needs `sqlalchemy.orm.attributes.flag_modified(m, "score_breakdown")` after assignment (assigning a NEW dict object, as above, is detected without it; keep the new-object assignment).

- [ ] **Step 6: Dry-run it against a COPY of the live DB**

```bash
mkdir -p /tmp/jdg-backfill && sqlite3 /Users/fuxinyao/quantheon/data/open_otc.sqlite3 ".backup '/tmp/jdg-backfill/copy.sqlite3'"
OPEN_OTC_ENV_FILE= OPEN_OTC_DATABASE_URL="sqlite+pysqlite:////tmp/jdg-backfill/copy.sqlite3" PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --all
OPEN_OTC_ENV_FILE= OPEN_OTC_DATABASE_URL="sqlite+pysqlite:////tmp/jdg-backfill/copy.sqlite3" PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --all --write
OPEN_OTC_ENV_FILE= OPEN_OTC_DATABASE_URL="sqlite+pysqlite:////tmp/jdg-backfill/copy.sqlite3" PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --all
```
Expected: first line `DRY RUN {"ok": N, …}` with no `REFUSING`; second `WROTE …`; third shows `already_present` ≈ the previous `ok` count. **Check that the output says the COPY was used** — the env var is `OPEN_OTC_DATABASE_URL` (not `DATABASE_URL`); a wrong name silently hits the live DB. Do NOT `--write` the live DB in this task.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/arena/process_metrics.py scripts/backfill_process_metrics.py tests/test_backfill_process_metrics.py
git commit -m "feat(arena): backfill JDG process evidence into historical matches (add-only)"
```

---

### Task 8: The validation study package

**Files:**
- Create: `scripts/arena_jdg_validation/stats.py` (pure), `scripts/arena_jdg_validation/extract.py`, `scripts/arena_jdg_validation/analyze.py`, `scripts/arena_jdg_validation/README.md`
- Test: `tests/test_jdg_validation_stats.py`

**Interfaces:**
- Consumes: backfilled `process` records; `scoring.waste_score/selection_score/calibration_score`.
- Produces: `stats.j0(process) -> float | None` (ungated mean); `stats.trap_correctness(trial_bd, trap_steps) -> float | None`; `stats.spearman(xs, ys) -> float | None`; `stats.heldout_pairs(rows) -> list[tuple]`; `stats.stratified_perm_p(pairs_by_stratum, draws=10000, seed=7) -> tuple[float, float]` (mean within-stratum ρ, one-sided p for ρ > 0); `stats.verdict(results) -> dict`.

- [ ] **Step 1: Write the failing tests**

```python
"""Pure statistics of the JDG validation (spec §6)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "arena_jdg_validation"))
import stats as v  # noqa: E402


def test_j0_is_ungated_mean_of_defined_subscores():
    p = {"scheme": "jdg-v1", "waste": {"repeats": 0, "dead_searches": 0, "denominator": 10},
         "selection": {"scored_steps": 2, "hits": 1},
         "calibration": {"trap_steps": [], "trap_reads": 0, "trap_n": 0,
                         "routine_reads": 3, "routine_n": 3}}
    assert v.j0(p) == (1.0 + 0.5) / 2
    assert v.j0({"unavailable": "x"}) is None


def test_trap_correctness_uses_only_trap_steps():
    bd = {"objective": {"steps": [
        {"index": 0, "checks": [{"passed": False}, {"passed": False}]},
        {"index": 1, "checks": [{"passed": True}, {"passed": False}]}]}}
    assert v.trap_correctness(bd, [1]) == 0.5
    assert v.trap_correctness(bd, []) is None


def test_spearman_basics():
    assert v.spearman([1, 2, 3], [10, 20, 30]) == 1.0
    assert v.spearman([1, 2, 3], [30, 20, 10]) == -1.0
    assert v.spearman([1, 1, 1], [1, 2, 3]) is None


def test_heldout_pairs_never_pair_a_trial_with_itself():
    rows = [{"match": 1, "trial": 0, "x": .2, "y": .9}, {"match": 1, "trial": 1, "x": .4, "y": .1},
            {"match": 2, "trial": 0, "x": .5, "y": .5}]
    pairs = v.heldout_pairs(rows)
    assert sorted(pairs) == sorted([(.2, .1), (.4, .9)])


def test_permutation_detects_a_strong_positive_and_not_noise():
    strong = {"wf": [(i, i + 0.1) for i in range(30)]}
    rho, p = v.stratified_perm_p(strong, draws=2000, seed=1)
    assert rho > 0.9 and p < 0.01
    import random
    rng = random.Random(3)
    noise = {"wf": [(rng.random(), rng.random()) for _ in range(30)]}
    _, p2 = v.stratified_perm_p(noise, draws=2000, seed=1)
    assert p2 > 0.05


def test_verdict_rule():
    ok = {"T1": (0.3, 0.01), "T1b": (0.3, 0.1), "T2": 0.6, "T3": 0.4}
    assert v.verdict(ok)["promote"] is True
    for bad in ({**ok, "T1": (0.3, 0.2)}, {**ok, "T1b": (0.3, 0.35)},
                {**ok, "T2": 0.4}, {**ok, "T3": 0.8}):
        assert v.verdict(bad)["promote"] is False
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_jdg_validation_stats.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'stats'`).

- [ ] **Step 3: Implement `stats.py`**

```python
"""Pure statistics for the JDG validation (spec 2026-10-06 §6). No DB, no IO."""
from __future__ import annotations

import random
from statistics import mean

from app.services.arena import scoring


def j0(process: dict | None) -> float | None:
    """Ungated judgment core: mean of the defined W, S, K (no correctness gate)."""
    subs = [x for x in (scoring.waste_score(process), scoring.selection_score(process),
                        scoring.calibration_score(process)) if x is not None]
    return sum(subs) / len(subs) if subs else None


def trap_correctness(trial_bd: dict, trap_steps: list[int]) -> float | None:
    checks = [c for s in (trial_bd.get("objective") or {}).get("steps") or []
              if s.get("index") in set(trap_steps) for c in s.get("checks") or []]
    return sum(bool(c["passed"]) for c in checks) / len(checks) if checks else None


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den


def heldout_pairs(rows: list[dict]) -> list[tuple[float, float]]:
    """(x of trial i, y of trial j) for every ordered pair i != j within a match."""
    by_match: dict = {}
    for r in rows:
        by_match.setdefault(r["match"], []).append(r)
    return [(a["x"], b["y"]) for trials in by_match.values()
            for a in trials for b in trials if a["trial"] != b["trial"]]


def _mean_rho(strata: dict[str, list[tuple[float, float]]]) -> float:
    vals = [r for r in (spearman([p[0] for p in ps], [p[1] for p in ps])
                        for ps in strata.values()) if r is not None]
    return mean(vals) if vals else 0.0


def stratified_perm_p(strata: dict[str, list[tuple[float, float]]],
                      draws: int = 10000, seed: int = 7) -> tuple[float, float]:
    """Mean within-stratum Spearman and its one-sided permutation p (H1: rho > 0)."""
    obs = _mean_rho(strata)
    rng = random.Random(seed)
    ge = 0
    for _ in range(draws):
        perm = {k: list(zip([p[0] for p in ps], rng.sample([p[1] for p in ps], len(ps))))
                for k, ps in strata.items()}
        ge += _mean_rho(perm) >= obs
    return obs, ge / draws


def verdict(results: dict) -> dict:
    """Spec §6 promotion rule. results: T1=(rho,p), T1b=(rho_cost,p_cost), T2=rho, T3=|rho|."""
    t1 = results["T1"][0] > 0 and results["T1"][1] < 0.05
    t1b = results["T1"][0] > results["T1b"][0]
    t2 = results["T2"] is not None and results["T2"] >= 0.5
    t3 = results["T3"] is not None and abs(results["T3"]) < 0.7
    return {"T1": t1, "T1b": t1b, "T2": t2, "T3": t3, "promote": t1 and t1b and t2 and t3}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_jdg_validation_stats.py -q`
Expected: PASS.

- [ ] **Step 5: Write `extract.py` and `analyze.py`**

`extract.py` — reads the arena DB (`--db` sqlite path, opened read-only via `file:…?mode=ro`), writes `trials.json`:
```python
"""Trial rows for the JDG validation: one per (match, trial), non-merged, scored."""
import argparse, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.arena.task import _is_infra_contaminated  # noqa: E402,F401  (documented filter)

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
rows = []
for mid, run, model, effort, wf, sb, cfg in db.execute(
        "select id, run_id, model_id, reasoning_effort, workflow_id, score_breakdown, config "
        "from arena_match where status='scored' "
        "and json_extract(config,'$.merged_from') is null"):
    bd = json.loads(sb or "{}")
    cfg = json.loads(cfg or "{}")
    frozen = cfg.get("provenance") or {}
    trials = bd.get("aggregate") or [bd]
    for i, t in enumerate(trials):
        proc = t.get("process")
        if not isinstance(proc, dict) or proc.get("scheme") != "jdg-v1":
            continue
        tc = ((t.get("diagnosis") or {}).get("counts_detail") or {}).get("tool_calls")
        rows.append({"match": mid, "run": run, "model": model, "effort": effort,
                     "workflow": wf, "trial": i, "process": proc,
                     "objective": t.get("objective"), "tool_calls": tc,
                     "par": frozen.get("par_tool_calls"),
                     "leak_era": wf == "high-board-portfolio-review-day" and 115 <= run <= 140})
Path(a.out).write_text(json.dumps(rows))
print(len(rows), "trial rows")
```
(Infra-contaminated trials never reach `scored` aggregates — `task._execute` skips them — so the import documents the filter rather than re-applying it; verify by reading `_is_infra_contaminated`'s callers and note the finding in README.)

`analyze.py` — loads `trials.json`, builds per-row `x = stats.j0(process)`, `y = stats.trap_correctness(row, process["calibration"]["trap_steps"])`, `cost = tool_calls / par` (rows without a par use the workflow's current `scoring.designed_par`); computes:
- T1: `stratified_perm_p` over `heldout_pairs` per workflow (x from trial i, y from trial j);
- T1b: same pairs with `cost` (sign-flipped, since more calls = worse) as x; record its ρ;
- T2: mean within-workflow Spearman over held-out pairs of (J₀ trial i, J₀ trial j);
- T3: mean within-workflow Spearman of (J₀, cost) over all trial rows, absolute value;
- each sub-score (W, S, K) on T1 and T2 alone;
- everything twice: all rows, and excluding `leak_era`;
and prints a Markdown report plus `stats.verdict(...)` as JSON to `--out`.
```python
"""Run the predeclared JDG validation and write a Markdown + JSON report."""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))
import stats as v  # noqa: E402
from app.services.arena import scoring  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--trials", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
rows = json.loads(Path(a.trials).read_text())


def run(rows, label):
    scorers = {"J0": v.j0, "W": scoring.waste_score, "S": scoring.selection_score,
               "K": scoring.calibration_score}
    out = {}
    for name, fn in scorers.items():
        pairs, rel, cost_pairs = defaultdict(list), defaultdict(list), defaultdict(list)
        by_match = defaultdict(list)
        for r in rows:
            x = fn(r["process"])
            y = v.trap_correctness(r, r["process"]["calibration"]["trap_steps"])
            if x is None or y is None or not r.get("tool_calls") or not r.get("par"):
                continue
            by_match[(r["workflow"], r["match"])].append(
                {"match": r["match"], "trial": r["trial"], "x": x, "y": y,
                 "cost": -(r["tool_calls"] / r["par"])})
        for (wf, _), trials in by_match.items():
            pairs[wf] += v.heldout_pairs(trials)
            rel[wf] += [(p["x"], q["x"]) for p in trials for q in trials if p["trial"] != q["trial"]]
            cost_pairs[wf] += v.heldout_pairs([{**t, "x": t["cost"]} for t in trials])
        t1 = v.stratified_perm_p(pairs)
        t1b = v.stratified_perm_p(cost_pairs)
        t2 = v._mean_rho(rel)
        t3_strata = defaultdict(list)
        for (wf, _), trials in by_match.items():
            t3_strata[wf] += [(t["x"], -t["cost"]) for t in trials]
        t3 = v._mean_rho(t3_strata)
        res = {"T1": t1, "T1b": t1b, "T2": t2, "T3": t3,
               "n_pairs": sum(len(p) for p in pairs.values())}
        res["verdict"] = v.verdict(res)
        out[name] = res
    return {label: out}


report = {**run(rows, "all"), **run([r for r in rows if not r["leak_era"]], "no_leak_era")}
Path(a.out).write_text(json.dumps(report, indent=1))
for label, res in report.items():
    print(f"## {label}")
    for name, r in res.items():
        print(f"- {name}: T1 rho {r['T1'][0]:+.3f} p {r['T1'][1]:.4f} | cost rho {r['T1b'][0]:+.3f} | "
              f"T2 {r['T2']:+.3f} | T3 {r['T3']:+.3f} | pairs {r['n_pairs']} | promote {r['verdict']['promote']}")
```
`README.md`: the spec §6 protocol verbatim (sample, predictor, outcome, held-out pairing, T1–T3, promotion rule, limitations), the two commands to run, and the note that constants are fixed by the spec.

- [ ] **Step 6: Smoke the pipeline on the backfilled COPY from Task 7**

```bash
PYTHONPATH=backend .venv/bin/python scripts/arena_jdg_validation/extract.py --db /tmp/jdg-backfill/copy.sqlite3 --out /tmp/jdg-backfill/trials.json
PYTHONPATH=backend .venv/bin/python scripts/arena_jdg_validation/analyze.py --trials /tmp/jdg-backfill/trials.json --out /tmp/jdg-backfill/report.json
```
Expected: a trial-row count in the hundreds and one report line per scorer for both `all` and `no_leak_era`. This is a smoke of the code path only — the result is read in Task 9.

- [ ] **Step 7: Commit**

```bash
git add scripts/arena_jdg_validation tests/test_jdg_validation_stats.py
git commit -m "feat(arena): predeclared JDG validation study (held-out, stratified permutation)"
```

---

### Task 9: Live backfill, the validation result, docs

**Files:**
- Create: `docs/arena/<YYYY-MM-DD>-jdg-validation.md`, dated with `date +%Y-%m-%d` on the day Step 4 runs
- Modify: `CHANGELOG.md` (`[Unreleased]`), `backend/app/golden_workflows/CLAUDE.md` (card section), `README.md` only if the arena card section names JDG

**Interfaces:**
- Consumes: everything above.
- Produces: the live DB carries `process` on every row it can; the validation verdict.

- [ ] **Step 1: Full test suites**

Run: `.venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | tail -5` (never pipe through `tail` without checking the exit code: re-run `echo $?` style via `; echo exit=$?`)
Run: `cd frontend && npm test -- --run && npx tsc --noEmit`
Expected: all green. Fix anything red before going on.

- [ ] **Step 2: Ask the user before writing the live DB**

Confirm no arena run is active (`sqlite3 -readonly data/open_otc.sqlite3 "select id,status from arena_run where status in ('queued','running')"` from the MAIN checkout, plus `ps aux | grep launch_arena`). Then ask the user, in-session, for the go-ahead to back up and `--write` the live DB, quoting the Task 7 dry-run tally. Do not proceed without an explicit yes.

- [ ] **Step 3: Back up, dry-run, write**

```bash
cd /Users/fuxinyao/quantheon
sqlite3 data/open_otc.sqlite3 ".backup 'data/open_otc.sqlite3.bak-pre-jdg-backfill-$(date +%Y%m%d)'"
cd /Users/fuxinyao/ootc-jdg
OPEN_OTC_ENV_FILE= OPEN_OTC_DATABASE_URL="sqlite+pysqlite:////Users/fuxinyao/quantheon/data/open_otc.sqlite3" PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --all
OPEN_OTC_ENV_FILE= OPEN_OTC_DATABASE_URL="sqlite+pysqlite:////Users/fuxinyao/quantheon/data/open_otc.sqlite3" PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --all --write
```
Expected: no `REFUSING`; `WROTE` tally matches the dry run.

- [ ] **Step 4: Run the validation on the live DB and write the report**

```bash
PYTHONPATH=backend .venv/bin/python scripts/arena_jdg_validation/extract.py --db /Users/fuxinyao/quantheon/data/open_otc.sqlite3 --out /tmp/jdg-trials.json
PYTHONPATH=backend .venv/bin/python scripts/arena_jdg_validation/analyze.py --trials /tmp/jdg-trials.json --out /tmp/jdg-report.json
```
Write `docs/arena/<date>-jdg-validation.md`: the protocol (link the spec §6), the sample (trial rows, matches, models, runs), the full results table for J₀, W, S, K under `all` and `no_leak_era`, the verdict per the predeclared rule, and the limitations. State the verdict plainly — a fail is a publishable negative result. Do not publish to artena.one (phase 2 decides the site).

- [ ] **Step 5: Docs**

`CHANGELOG.md` under `[Unreleased]`:
```markdown
### Added

- **JDG — an advisory judgment stat on the arena ability card** (spec
  `docs/superpowers/specs/2026-10-06-arena-jdg-judgment-stat-design.md`). Per trial, from the
  trial's own transcript: waste (same-step repeats, dead searches), selection (first domain
  call accepted by the step), calibration (read effort on `trap` steps vs routine), gated by
  correctness. Stored as raw counts (`score_breakdown.process`, scheme `jdg-v1`), backfilled
  into historical matches (add-only), and shown as an advisory chip — not in OVR, the
  tie-break or the radar until the predeclared validation passes (phase 2).
- **`trap: true` step labels** on seven steps across all six golden workflows; every manifest
  bumps `manifest_version`.

### Changed

- The arena card's jury score is renamed **`jdg` → `sbj`** (subjective; peer of the
  objective score). Same values and rules; no stored row carried a jury value.
```
`backend/app/golden_workflows/CLAUDE.md` card section: one paragraph — SBJ is the jury score (formerly JDG); JDG is the advisory judgment stat (top-level `card.jdg`, from `score_breakdown.process`); `trap: true` is scoring-relevant (bump `manifest_version`); S and K match transcript steps to the manifest by identical user text; constants are frozen by the spec.

- [ ] **Step 6: Commit**

```bash
git add docs/arena CHANGELOG.md backend/app/golden_workflows/CLAUDE.md
git commit -m "docs(arena): JDG phase-1 validation result, changelog, card guide"
```
