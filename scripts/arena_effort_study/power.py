import numpy as np
from scipy import stats
rng = np.random.default_rng(7)
def power(n_wf, n_eff, n_rep, sd, delta, sims=4000, alpha=0.05):
    hits = 0
    for _ in range(sims):
        mu = np.zeros((n_wf, n_eff)); mu[0, -1] += delta          # one task gains delta at top effort
        y = mu[..., None] + rng.normal(0, sd, (n_wf, n_eff, n_rep))
        cm = y.mean(2); gm = cm.mean(); rm = cm.mean(1, keepdims=True); em = cm.mean(0, keepdims=True)
        ss_int = n_rep * ((cm - rm - em + gm) ** 2).sum(); ss_err = ((y - cm[..., None]) ** 2).sum()
        df_i = (n_wf - 1) * (n_eff - 1); df_e = n_wf * n_eff * (n_rep - 1)
        F = (ss_int / df_i) / (ss_err / df_e)
        hits += stats.f.sf(F, df_i, df_e) < alpha
    return hits / sims
cases = [("deepseek-v4.1-flash #145 (low,max)", 6, 2, 3.43), ("gpt-6-luna #145 (low,med,xhigh)", 6, 3, 8.61),
         ("mimo-v2.6-flash #145 (low,med)", 6, 2, 5.24), ("gpt-5.6-luna #110 (4 arms)", 5, 4, 5.50)]
print(f"{'study':38s} sd   " + "  ".join(f"d={d:>2d}" for d in (5, 10, 15, 20, 30)) + "   80%-power delta")
for name, w, e, sd in cases:
    ps = [power(w, e, 2, sd, d, sims=2000) for d in (5, 10, 15, 20, 30)]
    lo, hi = 0.0, 60.0
    for _ in range(12):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if power(w, e, 2, sd, mid, sims=1500) < 0.8 else (lo, mid)
    print(f"{name:38s} {sd:4.1f} " + "  ".join(f"{p:5.2f}" for p in ps) + f"   ~{hi:4.1f} pts")
