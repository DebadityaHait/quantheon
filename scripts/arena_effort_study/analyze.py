"""Effort curves + the 'each task has its own best effort' test."""
import json, sys
from collections import defaultdict
import numpy as np
import pandas as pd

D = json.load(open(sys.argv[1]))
T = pd.DataFrame(D["trials"])
A = pd.DataFrame(D["arms"])
LADDER = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
rank = {e: i for i, e in enumerate(LADDER)}
rng = np.random.default_rng(20261002)
WF = {"risk-limit-breach-day": "rlb", "ops-settlement-day": "ops", "risk-manager-control-day": "rmc",
      "high-board-portfolio-review-day": "hb", "trader-rfq-booking-day": "rfq", "confirmation-desk-day": "conf"}
T["wf"] = T.workflow.map(WF); A["wf"] = A.workflow.map(WF)
T["usd"] = T.usd_low


# ---------------------------------------------------------------- 1. curves
def curves(study):
    t, a = T[T.study == study], A[A.study == study]
    rows = []
    for (m, e), g in t.groupby(["model", "effort"]):
        aa = a[(a.model == m) & (a.effort == e)]
        rows.append({"model": m, "effort": e, "n_wf": g.wf.nunique(), "n_trials": len(g),
                     "objective": aa.objective.mean(),
                     "ovr": np.mean([c["ovr"] for c in aa.card if c]),
                     "eff": np.mean([c["stats"]["EFF"] for c in aa.card if c]),
                     "con": np.nanmean([c.get("con") if c.get("con") is not None else np.nan for c in aa.card if c]),
                     "tool_calls": g.tool_calls.mean(), "model_calls": g.model_calls.mean(),
                     "reasoning_k": g.reasoning_tokens.mean() / 1e3 if g.reasoning_tokens.notna().any() else np.nan,
                     "output_k": g.output_tokens.mean() / 1e3, "usd": g.usd.mean(),
                     "wall_min": g.wall_s.mean() / 60})
    df = pd.DataFrame(rows)
    df["r"] = df.effort.map(rank)
    return df.sort_values(["model", "r"]).drop(columns="r")


def cell_table(study, value="objective"):
    a = A[A.study == study].copy()
    if value == "ovr":
        a["v"] = [c["ovr"] if c else np.nan for c in a.card]
    else:
        a["v"] = a.objective
    p = a.pivot_table(index=["model", "effort"], columns="wf", values="v")
    p = p[[w for w in WF.values() if w in p.columns]]
    p["_r"] = [rank[e] for _, e in p.index]
    return p.sort_values(["model", "_r"]).drop(columns="_r").round(1)


# ------------------------------------------------- 2. task-dependence tests
def design(t):
    wfs = sorted(t.wf.unique()); effs = sorted(t.effort.unique(), key=rank.get)
    return wfs, effs


def ols_fit(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return X @ beta


def interaction_ss(t, y):
    wfs, effs = design(t)
    W = (t.wf.to_numpy(dtype=object)[:, None] == np.array(wfs, dtype=object)[None, :]).astype(float)
    E = (t.effort.to_numpy(dtype=object)[:, None] == np.array(effs, dtype=object)[None, 1:]).astype(float)
    additive = np.hstack([W, E])
    cells = pd.Series(list(zip(t.wf, t.effort))).astype(str)
    C = pd.get_dummies(cells).values.astype(float)
    fa, fc = ols_fit(y, additive), ols_fit(y, C)
    ss_int = ((fc - fa) ** 2).sum()
    ss_err = ((y - fc) ** 2).sum()
    return ss_int, ss_err, fa


def interaction_test(t, col, n_perm=20000):
    """Freedman-Lane: permute residuals of the ADDITIVE model (workflow + effort)."""
    t = t.dropna(subset=[col])
    y = t[col].values.astype(float)
    ss_int, ss_err, fa = interaction_ss(t, y)
    resid = y - fa
    stat = ss_int / max(ss_err, 1e-9)
    null = []
    for _ in range(n_perm):
        yp = fa + rng.permutation(resid)
        si, se, _ = interaction_ss(t, yp)
        null.append(si / max(se, 1e-9))
    null = np.array(null)
    return {"stat": stat, "p": (1 + (null >= stat).sum()) / (1 + n_perm),
            "ss_int": ss_int, "ss_err": ss_err}


def cv_policy_gain(t, col):
    """Pick effort on one trial, score it on the other. Per-task vs one global effort.

    Ties at the pick go to the LOWER effort (cheaper). Only cells with both trials enter.
    """
    full = t.groupby(["wf", "effort"]).filter(lambda g: set(g.trial) >= {0, 1})
    res = []
    for pick, evalt in ((0, 1), (1, 0)):
        P = full[full.trial == pick].pivot_table(index="wf", columns="effort", values=col)
        E = full[full.trial == evalt].pivot_table(index="wf", columns="effort", values=col)
        effs = sorted(P.columns, key=rank.get)
        P, E = P[effs], E[effs]
        per_task = [E.loc[w, max(effs, key=lambda e: (P.loc[w, e], -rank[e]) if pd.notna(P.loc[w, e]) else (-1e9, 0))]
                    for w in P.index]
        g = max(effs, key=lambda e: (P[e].mean(), -rank[e]))
        res.append({"per_task": np.nanmean(per_task), "global": E[g].mean(), "global_pick": g,
                    "oracle": E.max(axis=1).mean()})
    return {k: (np.mean([r[k] for r in res]) if k != "global_pick" else [r[k] for r in res])
            for k in res[0]}


def cv_null(t, col, n_perm=5000):
    """Null for the CV gain under an additive model (no task-specific best)."""
    t = t.dropna(subset=[col]).reset_index(drop=True)
    y = t[col].values.astype(float)
    _, _, fa = interaction_ss(t, y)
    resid = y - fa
    obs = cv_policy_gain(t, col); obs_gain = obs["per_task"] - obs["global"]
    gains = []
    for _ in range(n_perm):
        tp = t.copy(); tp[col] = fa + rng.permutation(resid)
        r = cv_policy_gain(tp, col); gains.append(r["per_task"] - r["global"])
    gains = np.array(gains)
    return obs, obs_gain, (1 + (gains >= obs_gain).sum()) / (1 + n_perm), np.percentile(gains, [5, 50, 95])


def best_effort_per_task(t, col, tol=None):
    """Per workflow: best effort by cell mean, plus every effort within noise of it."""
    out = {}
    sd = t.groupby(["wf", "effort"])[col].std().dropna()
    noise = tol if tol is not None else float(np.sqrt((sd ** 2).mean()))
    for w, g in t.groupby("wf"):
        m = g.groupby("effort")[col].mean()
        best = m.max()
        within = sorted([e for e, v in m.items() if v >= best - noise], key=rank.get)
        out[w] = {"best": m.idxmax(), "best_score": round(best, 1),
                  "within_noise": within, "cheapest_within": within[0]}
    return out, noise


if __name__ == "__main__":
    pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
    report = {}
    for study in ("flash-trio", "luna56", "gemini38"):
        print(f"\n================ {study}: curves")
        c = curves(study); print(c.round(2).to_string(index=False))
        print(f"\n---- {study}: objective by cell"); print(cell_table(study).to_string())
        print(f"\n---- {study}: card OVR by cell"); print(cell_table(study, 'ovr').to_string())
        report[study] = {"curves": c.round(3).to_dict("records")}

    print("\n================ TASK-DEPENDENCE TESTS")
    tests = []
    configs = [("flash-trio", m, "#145 only (high excluded)") for m in sorted(T[T.study == "flash-trio"].model.unique())]
    configs += [("flash-trio", m, "#145 + re-used high") for m in sorted(T[T.study == "flash-trio"].model.unique())]
    configs += [("luna56", "gpt-5-6-luna", "#110")]
    for study, model, label in configs:
        t = T[(T.study == study) & (T.model == model)].copy()
        if label.startswith("#145 only"):
            t = t[t.run == 145]
        t = t.reset_index(drop=True)
        for col in ("objective", "card_ovr"):
            it = interaction_test(t, col)
            obs, gain, p_cv, band = cv_null(t, col)
            best, noise = best_effort_per_task(t, col)
            row = {"model": model, "set": label, "metric": col,
                   "efforts": sorted(t.effort.unique(), key=rank.get),
                   "interaction_p": round(it["p"], 4),
                   "cv_per_task": round(obs["per_task"], 2), "cv_global": round(obs["global"], 2),
                   "cv_oracle": round(obs["oracle"], 2), "global_picks": obs["global_pick"],
                   "cv_gain": round(gain, 2), "cv_gain_p": round(p_cv, 4),
                   "null_gain_5_50_95": [round(x, 2) for x in band],
                   "trial_noise_sd": round(noise, 2),
                   "best_per_task": {w: (b["best"], b["within_noise"]) for w, b in best.items()}}
            tests.append(row)
            print(json.dumps(row))
    report["tests"] = tests

    # Gemini: two efforts, low has one trial -> descriptive only
    g = A[A.study == "gemini38"].copy(); g["ovr"] = [c["ovr"] if c else np.nan for c in g.card]
    print("\n---- gemini38 xhigh - low (objective, ovr) by workflow:")
    p = g.pivot_table(index="wf", columns="effort", values=["objective", "ovr"])
    print((p.xs("xhigh", axis=1, level=1) - p.xs("low", axis=1, level=1)).round(1).to_string())

    json.dump(report, open(sys.argv[2], "w"), indent=1, default=str)
