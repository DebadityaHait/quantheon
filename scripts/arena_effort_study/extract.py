"""Trial-level dataset for the effort studies (#145 + re-used high, #110, #134/#138)."""
import json, sqlite3, sys
from datetime import datetime
from pathlib import Path

REPO = Path("/Users/fuxinyao/quantheon")
sys.path.insert(0, str(REPO / "backend"))
from app.services.arena.scoring import aggregate_card_from_trials  # noqa: E402

db = sqlite3.connect(f"file:{REPO}/data/open_otc.sqlite3?mode=ro", uri=True)
db.row_factory = sqlite3.Row


def study_of(row) -> str | None:
    run, wf, eff = row["run_id"], row["workflow_id"], row["reasoning_effort"]
    if run == 145:
        return "flash-trio"
    if run == 143 and eff == "high" and wf != "trader-rfq-booking-day":
        return "flash-trio"            # re-used high point (rfq v2 replaced by #144)
    if run == 144 and eff == "high":
        return "flash-trio"
    if run == 110:
        return "luna56"
    if run in (134, 138):
        return "gemini38"
    return None


def wall_seconds(path: Path) -> float | None:
    try:
        t = json.loads(path.read_text())
        a, b = t.get("started_at"), t.get("finished_at")
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()
    except Exception:  # noqa: BLE001
        return None


trials, arms = [], []
for row in db.execute("select * from arena_match where status='scored' and run_id in (110,134,138,143,144,145)"):
    study = study_of(row)
    if study is None:
        continue
    sb = json.loads(row["score_breakdown"])
    agg = sb.get("aggregate") or [sb]
    tdir = (REPO / row["transcript_path"]).parent if row["transcript_path"] else None
    cards = []
    for i, t in enumerate(agg):
        u = t.get("usage") or {}
        obj = t.get("objective") or {}
        checks = [(s["index"], c["label"], bool(c["passed"]), c.get("axis"))
                  for s in obj.get("steps") or [] for c in s.get("checks") or []]
        checks += [("success", c["label"], bool(c["passed"]), c.get("axis"))
                   for c in obj.get("success") or []]
        diag = (t.get("diagnosis") or {}).get("counts_detail") or {}
        card = t.get("card")
        if card:
            cards.append(card)
        tpath = tdir / (f"transcript.trial{i}.json" if len(agg) > 1 else "transcript.json") if tdir else None
        trials.append({
            "study": study, "run": row["run_id"], "match_id": row["id"],
            "model": row["model_id"], "effort": row["reasoning_effort"] or "default",
            "workflow": row["workflow_id"], "trial": i,
            "objective": t.get("objective_score"),
            "axes": obj.get("axes"),
            "card_ovr": (card or {}).get("ovr"), "card_stats": (card or {}).get("stats"),
            "tool_calls": diag.get("tool_calls"),
            "model_calls": u.get("calls"), "reasoning_tokens": u.get("reasoning"),
            "output_tokens": u.get("output"), "input_tokens": u.get("input"),
            "cache_read": u.get("cache_read"),
            "usd_low": u.get("usd_low"), "usd_high": u.get("usd_high"),
            "wall_s": wall_seconds(tpath) if tpath else None,
            "checks": checks,
        })
    folded = aggregate_card_from_trials(cards) if len(cards) > 1 else (
        {"ovr": cards[0]["ovr"], "con": None, "stats": cards[0]["stats"]} if cards else None)
    arms.append({"study": study, "run": row["run_id"], "match_id": row["id"],
                 "model": row["model_id"], "effort": row["reasoning_effort"] or "default",
                 "workflow": row["workflow_id"], "n_trials": len(agg),
                 "objective": row["objective_score"], "card": folded})

out = Path(sys.argv[1])
out.write_text(json.dumps({"trials": trials, "arms": arms}, indent=1))
from collections import Counter
print("trials", len(trials), Counter(t["study"] for t in trials))
print("arms", len(arms), Counter(a["study"] for a in arms))
missing = Counter((t["study"], k) for t in trials for k in ("reasoning_tokens", "wall_s", "card_ovr", "tool_calls") if t[k] is None)
print("missing fields:", dict(missing))
