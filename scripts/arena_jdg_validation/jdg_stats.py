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


def build_strata(rows: list[dict], scorer, par_of) -> dict:
    """Per-workflow held-out pairs for one predictor (spec §6).

    ``pairs``: (predictor of trial i, trap correctness of trial j); ``rel``: (predictor
    i, predictor j); ``cost_pairs``: (−calls/par of trial i, trap correctness of j);
    ``t3``: (predictor, calls/par) per trial. A row's par is its frozen provenance par,
    else ``par_of(workflow)`` (pre-stamp matches). A row with no par at all still
    contributes to ``pairs``/``rel`` — cost only feeds T1b and T3.
    """
    from collections import defaultdict

    by_match = defaultdict(list)
    for r in rows:
        x = scorer(r["process"])
        y = trap_correctness(r, r["process"]["calibration"]["trap_steps"])
        if x is None or y is None:
            continue
        par = r.get("par") or par_of(r["workflow"])
        tc = r.get("tool_calls")
        cost = -(tc / par) if par and isinstance(tc, (int, float)) else None
        by_match[(r["workflow"], r["match"])].append(
            {"match": r["match"], "trial": r["trial"], "x": x, "y": y, "cost": cost})
    out = {k: defaultdict(list) for k in ("pairs", "rel", "cost_pairs", "t3")}
    for (wf, _), trials in by_match.items():
        out["pairs"][wf] += heldout_pairs(trials)
        out["rel"][wf] += [(p["x"], q["x"]) for p in trials for q in trials
                           if p["trial"] != q["trial"]]
        costed = [t for t in trials if t["cost"] is not None]
        out["cost_pairs"][wf] += heldout_pairs([{**t, "x": t["cost"]} for t in costed])
        out["t3"][wf] += [(t["x"], -t["cost"]) for t in costed]
    return out


def model_level(rows: list[dict], min_n: int = 8) -> dict:
    """Per-model mean predictor (x) and trap correctness (y), and their Spearman ρ.

    Descriptive, NOT a predeclared test: models with fewer than ``min_n`` rows are
    dropped, and each row is one trial (not held out).
    """
    from collections import defaultdict

    by = defaultdict(list)
    for r in rows:
        by[r["model"]].append((r["x"], r["y"]))
    models = sorted(((m, len(v), mean(a for a, _ in v), mean(b for _, b in v))
                     for m, v in by.items() if len(v) >= min_n), key=lambda t: -t[2])
    return {"models": models,
            "rho": spearman([t[2] for t in models], [t[3] for t in models])}
