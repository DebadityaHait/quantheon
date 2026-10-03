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
    assert rec["scheme"] == "jdg-v1.1" and rec["manifest_version"] == 7
    assert rec["calibration"]["trap_steps"] == [0]


def test_safe_record_never_raises():
    # workflow=None makes process_record genuinely raise (no .steps), so this
    # exercises the except path; a well-formed odd step does NOT raise (robust).
    out = pm.safe_process_record([{"index": 0}], None)
    assert set(out) == {"unavailable"}
    assert out["unavailable"].startswith("AttributeError")


def test_accepts_matchstep_objects():
    from app.golden_workflows.transcript import MatchStep
    wf = _wf([("s0", ["get_portfolio"], False)])
    ms = MatchStep(index=0, user="s0", messages=[],
                   tool_calls=[{"id": "a", "name": "get_portfolio", "args": {}}],
                   tool_results=[{"name": "get_portfolio", "tool_call_id": "a", "content": {"raw": "x"}}],
                   skills_routed=[], artifacts=[], task_ids=[], response_text="", errors=[])
    assert pm.process_record([ms], wf)["selection"] == {"scored_steps": 1, "hits": 1}


def test_a_call_that_is_both_repeat_and_dead_counts_once():
    # spec §3.1: a call is wasted if it is a repeat OR a dead search — once, not twice
    wf = _wf([("s0", [], False)])
    steps = [_step(0, "s0", [("ls", {"path": "/x"}, "[]"), ("ls", {"path": "/x"}, "[]")])]
    w = pm.process_record(steps, wf)["waste"]
    assert w["wasted"] == 2 and w["denominator"] == 2


def test_record_answer_is_neither_numerator_nor_denominator():
    wf = _wf([("s0", [], False)])
    steps = [_step(0, "s0", [("record_answer", {"answer": {"a": 1}}, "ok"),
                             ("record_answer", {"answer": {"a": 1}}, "ok"),
                             ("get_portfolio", {}, "x")])]
    w = pm.process_record(steps, wf)["waste"]
    assert w["wasted"] == 0 and w["denominator"] == 1


def test_scheme_is_v1_1():
    assert pm.SCHEME == "jdg-v1.1"
