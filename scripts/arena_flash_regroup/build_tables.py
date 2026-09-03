#!/usr/bin/env python
"""Regroup arena runs into one flash-tier board, straight from the arena DB.

A "regroup" is NOT a merge: `store.merge_runs` refuses stamped matches whose manifest
hashes differ, and three of the six workflows differ between #143 and #146 by an
advisory `trap: true` label. Each cell is therefore taken from a DECLARED source run
(SOURCES below), never "the latest", and the report states every source and the
manifest/app stamp it carried.

Writes `<out>.tables.md` (deterministic blocks the report quotes) and `<out>.cells.json`.

    PYTHONPATH=backend python scripts/arena_flash_regroup/build_tables.py \
        --out docs/arena/2026-10-09-flash-quartet-haiku-55
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

REPO = Path.cwd()  # run from the repo root: the DB and artifacts are cwd-relative

TRIO = ("gpt-6-luna", "mimo-2-6-flash", "deepseek-v4-1-flash")
HAIKU = "claude-haiku-5-5"
MODELS = (HAIKU, *TRIO)
NAMES = {
    HAIKU: "claude-haiku-5.5",
    "gpt-6-luna": "gpt-6-luna",
    "mimo-2-6-flash": "mimo-v2.6-flash",
    "deepseek-v4-1-flash": "deepseek-v4.1-flash",
}
WORKFLOWS = (
    "risk-limit-breach-day",
    "ops-settlement-day",
    "risk-manager-control-day",
    "high-board-portfolio-review-day",
    "trader-rfq-booking-day",
    "confirmation-desk-day",
)
SHORT = {
    "risk-limit-breach-day": "risk-limit-breach",
    "ops-settlement-day": "ops-settlement",
    "risk-manager-control-day": "risk-manager-control",
    "high-board-portfolio-review-day": "high-board",
    "trader-rfq-booking-day": "trader-rfq",
    "confirmation-desk-day": "confirmation-desk",
}
# Workflows re-run for all four models together on a repaired manifest, and the run
# that holds them: #147 (high-board v4, trader-rfq v4, repaired 2026-10-08) and #148
# (risk-manager-control v3, seeded risk-run ids, 2026-10-09).
FIXED = {
    "high-board-portfolio-review-day": 147,
    "trader-rfq-booking-day": 147,
    "risk-manager-control-day": 148,
}
# risk-manager-control was run twice per model on the same v3 manifest. At the user's
# request each model's first pair (#148) is replaced by its second pair: Haiku's by #149
# (re-run first), the trio's by #150 (re-run to keep it fair). #148 is shown as the
# "first pair" column in the report, never mixed into a cell.
RMC_RERUN = {HAIKU: 149, "gpt-6-luna": 150, "mimo-2-6-flash": 150, "deepseek-v4-1-flash": 150}
RUNS = (143, 146, 147, 148, 149, 150)


def source_run(workflow: str, model: str) -> int:
    """The single run each cell is read from. Declared, not discovered."""
    if workflow == "risk-manager-control-day":
        return RMC_RERUN[model]
    if workflow in FIXED:
        return FIXED[workflow]
    return 146 if model == HAIKU else 143


def _calls(bd: dict) -> float | None:
    vals = [
        (t.get("diagnosis") or {}).get("counts_detail", {}).get("tool_calls")
        for t in (bd.get("aggregate") or [])
    ]
    vals = [v for v in vals if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else None


# Haiku 5.5's list price carries no cache-write rate. The gateway's own billing
# breakdown for one live call (2026-10-09) shows `input_cache_write_5_min` at 0.125
# USD/MTok (1.25x the 0.10 prompt rate) and `input_cache_write_1_h` at 0.20. The
# 5-minute rate is assumed: the arena sets no cache TTL, so the default applies.
# The list's prompt rate steps from 0.10 to 0.50 at a 100k-token prompt; the write rate
# is stepped the same way (0.125 -> 0.625, the same 1.25x). The 0.625 is INFERRED, not
# measured, and applies to only 7 of Haiku's 1,014 calls (about 80k cache-write tokens).
HAIKU_KEY = "anthropic/claude-haiku-5.5"
HAIKU_CACHE_WRITE_5M = [
    {"usd_per_mtok": 0.125, "min_prompt_ktok": 0.0},
    {"usd_per_mtok": 0.625, "min_prompt_ktok": 100.0},
]


def _billing_cache(run: int) -> dict:
    path = REPO / "artifacts" / "arena" / str(run) / "billing.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _price_trials(run: int, workflow: str, model: str) -> dict:
    """Cost of one cell: list low/high, the 'today' figure, and the BILLED amount.

    `today` is the figure the report quotes: the list price, with two measured
    corrections. Deepseek's route lists two input prices and the gateway billed the
    LOWER on every call, so the low end is used. Haiku's missing cache-write rate is
    filled from the billing breakdown above.
    `billed` sums the gateway's per-generation `billAmount` over the ids this cell
    recorded (None when it recorded none).
    """
    from app.services.arena.cost import _model_key, price_call, pricing_snapshot

    models = pricing_snapshot()["models"]
    cache = _billing_cache(run)
    lo = hi = today = billed = 0.0
    trials = calls = ids = found = 0
    seen: set[str] = set()
    pattern = f"artifacts/arena/{run}/{workflow}/{model}/*/transcript.trial*.json"
    for path in sorted(glob.glob(str(REPO / pattern))):
        trials += 1
        for step in json.load(open(path))["steps"]:
            for c in step.get("usage") or []:
                calls += 1
                key = _model_key(c.get("model"))
                rates = models.get(key)
                p = price_call(c, rates) if rates else None
                if p is None:
                    raise SystemExit(f"unpriced call in {path}: {c.get('model')}")
                lo += p[0]
                hi += p[1]
                if rates and key == HAIKU_KEY and not rates.get("input_cache_write"):
                    fixed = price_call(c, {**rates, "input_cache_write": HAIKU_CACHE_WRITE_5M})
                    today += fixed[0] if fixed else p[0]
                else:
                    today += p[0]
                gid = c.get("generation_id")
                if gid and gid not in seen:
                    seen.add(gid)
                    ids += 1
                    if "usd" in cache.get(gid, {}):
                        found += 1
                        billed += cache[gid]["usd"]
    return {"lo": lo, "hi": hi, "today": today, "trials": trials, "calls": calls,
            "billed": billed if found else None, "ids": ids, "found": found}


def collect() -> dict:
    from app.database import SessionLocal
    from app.services.arena import store

    session = SessionLocal()
    try:
        runs = {r: store.get_run(session, r) for r in RUNS}
        provenance = {
            r: {"app": ((d or {}).get("provenance") or {}).get("app", {}).get("git_sha"),
                "manifests": ((d or {}).get("provenance") or {}).get("manifests", {})}
            for r, d in runs.items()
        }
        cells: dict = {}
        for wf in WORKFLOWS:
            for model in MODELS:
                run = source_run(wf, model)
                m = [x for x in (runs[run] or {})["matches"]
                     if x["workflow_id"] == wf and x["model_id"] == model]
                if len(m) != 1:
                    raise SystemExit(f"{wf}/{model} in #{run}: expected 1 match, got {len(m)}")
                m = m[0]
                if m["status"] != "scored":
                    raise SystemExit(f"{wf}/{model} in #{run}: status {m['status']}")
                if (m.get("reasoning_effort") or "") != "high":
                    raise SystemExit(f"{wf}/{model} in #{run}: effort {m.get('reasoning_effort')}")
                bd = m["score_breakdown"]
                card = bd.get("card") or {}
                pr = _price_trials(run, wf, model)
                cells[(wf, model)] = {
                    "run": run,
                    "obj": m["objective_score"],
                    "trials": [round(t["objective_score"], 1) if t.get("objective_score") is not None
                               else round(t["total_score"], 1) for t in bd["aggregate"]],
                    "ovr": card.get("ovr"), "stats": card.get("stats") or {}, "con": card.get("con"),
                    "tool_calls": _calls(bd),
                    "usd_lo": pr["lo"], "usd_hi": pr["hi"], "usd_today": pr["today"],
                    "usd_trials": pr["trials"], "llm_calls": pr["calls"],
                    "billed": pr["billed"], "billed_ids": pr["ids"], "billed_found": pr["found"],
                    "n_trials": bd.get("n_trials"),
                }
        return {"cells": cells, "provenance": provenance}
    finally:
        session.close()


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def render(data: dict) -> str:
    from app.services.arena.cost import pricing_snapshot

    cells, prov = data["cells"], data["provenance"]
    snap = pricing_snapshot()
    L: list[str] = [
        f"<!-- generated by scripts/arena_flash_regroup/build_tables.py; "
        f"pricing snapshot {snap['fetched_at']} sha256 {snap['sha256'][:12]} -->", ""]

    def c(wf, m):
        return cells[(wf, m)]

    # ---- headline: consolidated card = mean of the six workflow cards
    L += ["### Headline — mean of each model's six workflow cards", "",
          "| Model | OVR | GRD | ADH | SYN | PRC | EFF | CON | Objective | Tool calls / match |",
          "|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|"]
    order = sorted(MODELS, key=lambda m: -(_mean([c(w, m)["ovr"] for w in WORKFLOWS]) or 0))
    for m in order:
        rows = [c(w, m) for w in WORKFLOWS]
        stat = lambda k: _mean([r["stats"].get(k) for r in rows])  # noqa: E731
        L.append(
            f"| **{NAMES[m]}** | **{_mean([r['ovr'] for r in rows]):.1f}** | {stat('GRD'):.0f} | "
            f"{stat('ADH'):.0f} | {stat('SYN'):.0f} | {stat('PRC'):.0f} | {stat('EFF'):.0f} | "
            f"{_mean([r['con'] for r in rows]):.0f} | {_mean([r['obj'] for r in rows]):.1f} | "
            f"{_mean([r['tool_calls'] for r in rows]):.0f} |")
    L.append("")

    # ---- sensitivity: drop risk-manager-control (kept so the earlier board's column stays comparable)
    L += ["### Sensitivity — the same table without risk-manager-control-day", "",
          "| Model | OVR (6 workflows) | OVR (5) | Objective (6) | Objective (5) |",
          "|---|:--:|:--:|:--:|:--:|"]
    five = [w for w in WORKFLOWS if w != "risk-manager-control-day"]
    for m in order:
        L.append(
            f"| {NAMES[m]} | {_mean([c(w, m)['ovr'] for w in WORKFLOWS]):.1f} | "
            f"{_mean([c(w, m)['ovr'] for w in five]):.1f} | "
            f"{_mean([c(w, m)['obj'] for w in WORKFLOWS]):.1f} | "
            f"{_mean([c(w, m)['obj'] for w in five]):.1f} |")
    L.append("")

    # ---- per workflow objective, trials, CON
    L += ["### Workflow by workflow — objective (trial 1 / trial 2) · CON", "",
          "| Workflow | source | " + " | ".join(NAMES[m] for m in MODELS) + " |",
          "|---|---|" + ":--:|" * len(MODELS)]
    for w in WORKFLOWS:
        best = max(c(w, m)["obj"] for m in MODELS)
        cols = []
        for m in MODELS:
            r = c(w, m)
            t = " / ".join(f"{x:g}" for x in r["trials"])
            val = f"{r['obj']:.1f}"
            cols.append((f"**{val}**" if r["obj"] == best else val) + f" ({t}) · {r['con']}")
        src = ("#149 + #150" if w == "risk-manager-control-day"
               else f"#{FIXED[w]}" if w in FIXED else "#143 + #146")
        L.append(f"| {SHORT[w]} | {src} | " + " | ".join(cols) + " |")
    L.append("")

    # ---- per workflow OVR and EFF
    L += ["### Workflow cards — OVR · EFF", "",
          "| Workflow | " + " | ".join(NAMES[m] for m in MODELS) + " |",
          "|---|" + ":--:|" * len(MODELS)]
    for w in WORKFLOWS:
        L.append(f"| {SHORT[w]} | " + " | ".join(
            f"{c(w, m)['ovr']} · {c(w, m)['stats'].get('EFF')}" for m in MODELS) + " |")
    L.append("")

    # ---- tool calls per match
    L += ["### Tool calls per match (mean of two trials)", "",
          "| Workflow | par | " + " | ".join(NAMES[m] for m in MODELS) + " |",
          "|---|:--:|" + ":--:|" * len(MODELS)]
    par = {w: None for w in WORKFLOWS}
    for r in prov.values():
        for w, mm in r["manifests"].items():
            par[w] = mm.get("par_tool_calls") or par.get(w)
    for w in WORKFLOWS:
        L.append(f"| {SHORT[w]} | {par[w]} | " + " | ".join(
            f"{c(w, m)['tool_calls']:.0f}" for m in MODELS) + " |")
    L.append("")

    # ---- cost
    L += [f"### Cost — two trials per cell, today's rates (snapshot {snap['fetched_at']})", "",
          "| Workflow | " + " | ".join(NAMES[m] for m in MODELS) + " |",
          "|---|" + ":--:|" * len(MODELS)]
    for w in WORKFLOWS:
        L.append(f"| {SHORT[w]} | " + " | ".join(
            f"${c(w, m)['usd_today']:.3f}" for m in MODELS) + " |")
    L.append("| **Twelve matches** | " + " | ".join(
        f"**${sum(c(w, m)['usd_today'] for w in WORKFLOWS):.2f}**" for m in MODELS) + " |")
    L.append("")

    L += ["### Cost — what the gateway billed, against the same cells at today's rates", "",
          "| Model | Billed, as run | Today's rates | Calls billed | Basis |",
          "|---|:--:|:--:|:--:|---|"]
    for m in MODELS:
        today = sum(c(w, m)["usd_today"] for w in WORKFLOWS)
        ids = sum(c(w, m)["billed_ids"] for w in WORKFLOWS)
        found = sum(c(w, m)["billed_found"] for w in WORKFLOWS)
        whole = [w for w in WORKFLOWS if c(w, m)["billed_ids"] and c(w, m)["billed_found"] >= c(w, m)["billed_ids"] - 3]
        if len(whole) == len(WORKFLOWS):
            billed = sum(c(w, m)["billed"] or 0.0 for w in WORKFLOWS)
            L.append(f"| {NAMES[m]} | ${billed:.2f} | ${today:.2f} | {found} of {ids} | per-call bill |")
        elif whole:
            billed = sum(c(w, m)["billed"] or 0.0 for w in whole)
            est = sum(c(w, m)["usd_today"] for w in whole)
            L.append(f"| {NAMES[m]} | ${billed:.2f} on {len(whole)} of {len(WORKFLOWS)} workflows "
                     f"(estimate there: ${est:.2f}) | ${today:.2f} | {found} of {ids} | "
                     f"per-call bill on {', '.join(SHORT[w] for w in whole)}; estimate elsewhere |")
        else:
            L.append(f"| {NAMES[m]} | not recorded | ${today:.2f} | 0 | rate-verified estimate |")
    L.append("")

    # The check that justifies reading deepseek's LOW list price as its true price.
    ds = "deepseek-v4-1-flash"
    L += ["### Check — deepseek billed against its list prices", "",
          "| Workflow | Run | Billed | List, low end | Ratio |", "|---|:--:|:--:|:--:|:--:|"]
    for w in WORKFLOWS:
        r = c(w, ds)
        if r["billed"] is not None and r["billed_found"] == r["billed_ids"]:
            ref = r["usd_lo"]
            L.append(f"| {SHORT[w]} | #{r['run']} | ${r['billed']:.4f} | ${ref:.4f} | "
                     f"{r['billed'] / ref:.2f} |")
    L.append("")

    # ---- provenance of every cell
    L += ["### What each cell ran on", "",
          "| Run | App build | Workflows (manifest version · sha256[:8]) |", "|---|---|---|"]
    for run in RUNS:
        p = prov[run]
        used = sorted({w for w in WORKFLOWS for m in MODELS if c(w, m)["run"] == run})
        L.append(f"| #{run} | `{(p['app'] or '?')[:9]}` | " + "; ".join(
            f"{SHORT[w]} v{p['manifests'][w]['manifest_version']} · "
            f"`{str(p['manifests'][w]['sha256'])[:8]}`" for w in used) + " |")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Path stem, no extension")
    args = ap.parse_args()
    data = collect()
    out = REPO / args.out
    out.with_suffix(".tables.md").write_text(render(data))
    flat = {f"{w}|{m}": v for (w, m), v in data["cells"].items()}
    out.with_suffix(".cells.json").write_text(json.dumps(flat, indent=1, default=str))
    print(out.with_suffix(".tables.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
