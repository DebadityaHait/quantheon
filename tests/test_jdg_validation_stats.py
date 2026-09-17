"""Pure statistics of the JDG validation (spec §6)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "arena_jdg_validation"))
import jdg_stats as v  # noqa: E402


def test_j0_is_ungated_mean_of_defined_subscores():
    p = {"scheme": "jdg-v1.1", "waste": {"repeats": 0, "dead_searches": 0, "wasted": 0, "denominator": 10},
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
    ok = {"T1": (0.3, 0.01), "T1b": (0.1, 0.1), "T2": 0.6, "T3": 0.4}   # J0 beats cost
    assert v.verdict(ok)["promote"] is True
    for bad in ({**ok, "T1": (0.3, 0.2)}, {**ok, "T1b": (0.3, 0.35)},
                {**ok, "T2": 0.4}, {**ok, "T3": 0.8}):
        assert v.verdict(bad)["promote"] is False


def test_extract_skips_non_dict_trials(tmp_path):
    import json
    import sqlite3
    import subprocess

    db = tmp_path / "a.sqlite3"
    con = sqlite3.connect(db)
    con.execute("create table arena_match (id integer, run_id integer, model_id text, "
                "reasoning_effort text, workflow_id text, status text, score_breakdown text, "
                "config text)")
    good = {"scheme": "jdg-v1.1"}
    rows = [
        (1, 9, "m", "high", "wf", "scored",
         json.dumps({"n_trials": 2, "aggregate": [{"process": good}, {"process": good}]}), "{}"),
        (2, 9, "m", "high", "wf", "scored",
         json.dumps({"n_trials": 2, "aggregate": [{"process": good}, "x"]}), "{}"),
        # legacy "repeats" era (runs 8/9): aggregate is a summary dict, or even `true`;
        # the row is a single legacy trial with its process at the top level
        (3, 8, "m", "high", "wf", "scored",
         json.dumps({"aggregate": {"mean": 1.0}, "process": good}), "{}"),
        (4, 8, "m", "high", "wf", "scored",
         json.dumps({"aggregate": True, "process": good}), "{}"),
    ]
    con.executemany("insert into arena_match values (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    out = tmp_path / "t.json"
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / "scripts/arena_jdg_validation/extract.py"),
                    "--db", str(db), "--out", str(out)], check=True,
                   env={"PYTHONPATH": str(root / "backend"), "OPEN_OTC_ENV_FILE": "",
                        "PATH": "/usr/bin:/bin"})
    got = json.loads(out.read_text())
    assert [(r["match"], r["trial"]) for r in got] == [(1, 0), (1, 1), (2, 0), (3, 0), (4, 0)]


def test_build_strata_uses_fallback_par_for_prestamp_rows():
    proc = {"scheme": "jdg-v1.1", "waste": {"repeats": 0, "dead_searches": 0, "wasted": 0, "denominator": 10},
            "selection": {"scored_steps": 1, "hits": 1},
            "calibration": {"trap_steps": [1], "trap_reads": 2, "trap_n": 1,
                            "routine_reads": 2, "routine_n": 1}}
    obj = {"steps": [{"index": 1, "checks": [{"passed": True}]}]}
    rows = [{"workflow": "wf", "match": 7, "trial": t, "process": proc, "objective": obj,
             "tool_calls": 30 + t, "par": None} for t in (0, 1)]
    s = v.build_strata(rows, v.j0, par_of=lambda wf: 24)
    assert len(s["pairs"]["wf"]) == 2 and len(s["cost_pairs"]["wf"]) == 2
    # without a par anywhere, the J0 pairs survive; only the cost-based ones drop
    s2 = v.build_strata(rows, v.j0, par_of=lambda wf: None)
    assert len(s2["pairs"]["wf"]) == 2 and s2["cost_pairs"]["wf"] == []


def test_model_level_means_and_rank_correlation():
    def row(model, x, y):
        return {"model": model, "x": x, "y": y}
    rows = [row("a", .9, .1)] * 8 + [row("b", .5, .5)] * 8 + [row("c", .1, .9)] * 8 + [row("d", .3, .3)] * 3
    out = v.model_level(rows, min_n=8)
    assert [m for m, *_ in out["models"]] == ["a", "b", "c"]       # d has < 8 rows
    assert out["rho"] == -1.0
