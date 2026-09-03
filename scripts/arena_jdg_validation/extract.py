"""Trial rows for the JDG validation: one per (match, trial), non-merged, scored."""
import argparse, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.arena.task import _is_infra_contaminated  # noqa: E402,F401  (documented filter)
from app.services.arena.process_metrics import SCHEME  # noqa: E402

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
    # A list of trial dicts, or a legacy row (runs 8/9 stored a summary dict, even `true`).
    agg = bd.get("aggregate")
    trials = agg if isinstance(agg, list) and agg else [bd]
    for i, t in enumerate(trials):
        if not isinstance(t, dict):        # a malformed aggregate slot — never a trial row
            continue
        proc = t.get("process")
        if not isinstance(proc, dict) or proc.get("scheme") != SCHEME:
            continue
        tc = ((t.get("diagnosis") or {}).get("counts_detail") or {}).get("tool_calls")
        rows.append({"match": mid, "run": run, "model": model, "effort": effort,
                     "workflow": wf, "trial": i, "process": proc,
                     "objective": t.get("objective"), "tool_calls": tc,
                     "par": frozen.get("par_tool_calls"),
                     "leak_era": wf == "high-board-portfolio-review-day" and 115 <= run <= 140})
Path(a.out).write_text(json.dumps(rows))
print(len(rows), "trial rows")
