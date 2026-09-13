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
    assert why == "ok" and new["process"]["scheme"] == "jdg-v1.1"
    assert {k: v for k, v in new.items() if k != "process"} == bd
    assert "process" not in bd                       # input not mutated


def test_multi_trial_each_trial_gets_its_own_record_and_card_core_is_identical():
    bd = {"n_trials": 2, "aggregate": [_trial(), _trial()]}
    before = copy.deepcopy(bd)
    new, why = pm.backfill_breakdown(bd, [STEPS, None], WF)
    assert why == "ok"
    assert new["aggregate"][0]["process"]["scheme"] == "jdg-v1.1"
    assert new["aggregate"][1]["process"] == {"unavailable": "transcript_missing"}
    old_card, _ = _match_card(before, "high-board-portfolio-review-day",
                              frozen={"par_tool_calls": 24, "par_calibrated": True})
    new_card, _ = _match_card(new, "high-board-portfolio-review-day",
                              frozen={"par_tool_calls": 24, "par_calibrated": True})
    for key in ("ovr", "base_ovr", "con", "stats", "position", "sbj"):
        assert old_card.get(key) == new_card.get(key), key


def test_already_backfilled_is_skipped():
    bd = {**_trial(), "process": {"scheme": "jdg-v1.1"}}
    assert pm.backfill_breakdown(bd, [STEPS], WF) == (None, "already_present")


def test_missing_reason_is_recorded():
    new, _ = pm.backfill_breakdown(_trial(), [None], WF, missing_reason="merged_run")
    assert new["process"] == {"unavailable": "merged_run"}


def test_map_trial_transcripts_unique_matches_only():
    # trial0 stored 12 calls, trial1 stored 30; files: trial0 was infra-gated (7 calls)
    assert pm.map_trial_transcripts([12, 30], [7, 12, 30]) == [1, 2]
    # tied counts: positional is PROVABLY right when there are exactly as many files
    # as clean trials and every position's count agrees (no infra trial was skipped)
    assert pm.map_trial_transcripts([12, 12], [12, 12]) == [0, 1]
    assert pm.map_trial_transcripts([12, 12], [12, 12, 5]) == [None, None]   # ambiguous
    assert pm.map_trial_transcripts([12, 12], [12, 7]) == [None, None]       # ambiguous
    assert pm.map_trial_transcripts([12, None], [12, 5]) == [0, None]
    assert pm.map_trial_transcripts([9], [12]) == [None]


def test_backfill_skips_malformed_aggregate():
    assert pm.backfill_breakdown({"n_trials": 2, "aggregate": [_trial()]}, [STEPS], WF) \
        == (None, "malformed_aggregate")
    assert pm.backfill_breakdown({"n_trials": 2, "aggregate": [_trial(), "x"]}, [STEPS, STEPS], WF) \
        == (None, "malformed_aggregate")


def test_aggregate_row_gets_process_per_trial_only():
    # Matches write time (Task 5 ruling): evidence lives in aggregate[i]; the top
    # level of an aggregate row is the fold and carries no process.
    bd = {"n_trials": 1, "aggregate": [_trial()]}
    new, why = pm.backfill_breakdown(bd, [STEPS], WF)
    assert why == "ok" and new["aggregate"][0]["process"]["scheme"] == "jdg-v1.1"
    assert "process" not in new


def _load_cli():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "backfill_process_metrics.py"
    spec = importlib.util.spec_from_file_location("backfill_cli", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _transcript(n_calls):
    calls = [{"id": f"c{i}", "name": "get_portfolio", "args": {"i": i}} for i in range(n_calls)]
    return {"schema_version": 1, "run_id": None, "workflow_id": "risk-limit-breach-day",
            "model_id": "m", "started_at": None, "finished_at": None,
            "steps": [{"index": 0, "user": "u", "messages": [], "tool_calls": calls,
                       "tool_results": [], "skills_routed": [], "artifacts": [],
                       "task_ids": [], "response_text": "", "errors": []}]}


def test_trial_steps_resolve_against_repo_root_and_map_by_count(tmp_path):
    import json
    from app.golden_workflows.registry import get_workflow_bundle
    from app.golden_workflows.transcript import MatchTranscript
    from app.services.arena.scoring import diagnose_heuristic

    cli = _load_cli()
    loaded = get_workflow_bundle("risk-limit-breach-day")
    d = tmp_path / "artifacts" / "arena" / "1" / "wf" / "m" / "high"
    d.mkdir(parents=True)
    # file trial0 = an infra-gated trial (2 calls); the two CLEAN trials are 5 and 3
    for k, n in enumerate([2, 5, 3]):
        (d / f"transcript.trial{k}.json").write_text(json.dumps(_transcript(n)))
    (d / "transcript.json").write_text(json.dumps(_transcript(3)))
    count = lambda n: diagnose_heuristic(MatchTranscript.model_validate(_transcript(n)),
                                         loaded)["tool_calls"]
    stored = [count(5), count(3)]                      # aggregate order: clean trials
    rel = "artifacts/arena/1/wf/m/high/transcript.json"  # relative, like real rows
    steps = cli._trial_steps(rel, stored, loaded, repo_root=tmp_path)
    assert [len(s[0]["tool_calls"]) for s in steps] == [5, 3]
    # resolved against the wrong root -> nothing found -> honest None, never a guess
    assert cli._trial_steps(rel, stored, loaded, repo_root=tmp_path / "elsewhere") == [None, None]


def test_unavailable_records_are_retried_but_real_records_are_frozen():
    stale = {"n_trials": 2, "aggregate": [{**_trial(), "process": {"unavailable": "transcript_missing"}},
                                          {**_trial(), "process": {"scheme": "jdg-v1.1", "frozen": 1}}]}
    new, why = pm.backfill_breakdown(stale, [STEPS, STEPS], WF)
    assert why == "ok"
    assert new["aggregate"][0]["process"]["scheme"] == "jdg-v1.1"          # retried
    assert new["aggregate"][1]["process"] == {"scheme": "jdg-v1.1", "frozen": 1}  # untouched
    legacy = {**_trial(), "process": {"unavailable": "transcript_missing"}}
    new2, why2 = pm.backfill_breakdown(legacy, [STEPS], WF)
    assert why2 == "ok" and new2["process"]["scheme"] == "jdg-v1.1"


def test_older_scheme_records_are_replaced_current_ones_frozen():
    stale = {**_trial(), "process": {"scheme": "jdg-v1", "waste": {}}}
    new, why = pm.backfill_breakdown(stale, [STEPS], WF)
    assert why == "ok" and new["process"]["scheme"] == pm.SCHEME
    current = {**_trial(), "process": {"scheme": pm.SCHEME}}
    assert pm.backfill_breakdown(current, [STEPS], WF) == (None, "already_present")
