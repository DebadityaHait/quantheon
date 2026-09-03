"""Run the predeclared JDG validation and write a Markdown + JSON report."""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))
import jdg_stats as v  # noqa: E402
from app.services.arena import scoring  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--trials", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
rows = json.loads(Path(a.trials).read_text())


_PARS: dict = {}


def par_of(workflow_id):
    """Current designed par — the fallback for pre-stamp rows with no frozen par."""
    if workflow_id not in _PARS:
        from app.golden_workflows.registry import get_workflow
        try:
            _PARS[workflow_id] = scoring.designed_par(get_workflow(workflow_id))
        except Exception:  # noqa: BLE001
            _PARS[workflow_id] = None
    return _PARS[workflow_id]


def run(rows, label):
    scorers = {"J0": v.j0, "W": scoring.waste_score, "S": scoring.selection_score,
               "K": scoring.calibration_score}
    out = {}
    for name, fn in scorers.items():
        st = v.build_strata(rows, fn, par_of)
        res = {"T1": v.stratified_perm_p(st["pairs"]), "T1b": v.stratified_perm_p(st["cost_pairs"]),
               "T2": v._mean_rho(st["rel"]), "T3": v._mean_rho(st["t3"]),
               "n_pairs": sum(len(p) for p in st["pairs"].values()),
               "n_cost_pairs": sum(len(p) for p in st["cost_pairs"].values())}
        res["verdict"] = v.verdict(res)
        out[name] = res
    return {label: out}


report = {**run(rows, "all"), **run([r for r in rows if not r["leak_era"]], "no_leak_era")}
# Descriptive model-level view (not a predeclared test): per-trial J0 vs trap correctness.
ml_rows = []
for r in rows:
    x = v.j0(r["process"])
    y = v.trap_correctness(r, r["process"]["calibration"]["trap_steps"])
    if x is not None and y is not None:
        ml_rows.append({"model": r["model"], "x": x, "y": y})
report["model_level"] = v.model_level(ml_rows)
Path(a.out).write_text(json.dumps(report, indent=1))
ml = report["model_level"]
print(f"## model_level (descriptive) rho {ml['rho']:+.3f} over {len(ml['models'])} models")
for m, n, x, y in ml["models"]:
    print(f"  {m:28} n={n:3} J0={x:.2f} trap={y:.2f}")
for label, res in report.items():
    if label == "model_level":
        continue
    print(f"## {label}")
    for name, r in res.items():
        print(f"- {name}: T1 rho {r['T1'][0]:+.3f} p {r['T1'][1]:.4f} | cost rho {r['T1b'][0]:+.3f} | "
              f"T2 {r['T2']:+.3f} | T3 {r['T3']:+.3f} | pairs {r['n_pairs']} (cost {r['n_cost_pairs']}) | promote {r['verdict']['promote']}")
