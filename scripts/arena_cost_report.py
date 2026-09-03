#!/usr/bin/env python3
"""Per-match tokens and cost for one arena run.

Default: the list-price estimate each match stored at score time
(``score_breakdown.usage``, see ``backend/app/services/arena/cost.py``).

``--billed``: also look up what ZenMux actually BILLED. Every LLM call records
the gateway's generation id in the match transcript; this sums
``ratingResponses.billAmount`` from ``GET /api/v1/management/generation?id=…``
for each one. Billing lands 3–5 minutes after a call, so run it a few minutes
after the board finishes. The key is read from ``ZENMUX_MANAGEMENT_KEY`` (the
name ``.env`` / ``.env.example`` use; the older ``ZENMUX_MGT_KEY`` still works),
from the process environment first and then from the repo's ``.env``, and is
never printed or stored. Lookups are cached in
``artifacts/arena/<run>/billing.json`` (amounts only), so a re-run only asks
for ids it has not seen.

Usage:
    OPEN_OTC_DATABASE_URL=sqlite:////abs/path/open_otc.sqlite3 \\
        python scripts/arena_cost_report.py --run 141 [--billed]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BILLING_URL = "https://zenmux.ai/api/v1/management/generation?id={}"
# Canonical name first (what `.env.example` documents), then the legacy spelling.
KEY_NAMES = ("ZENMUX_MANAGEMENT_KEY", "ZENMUX_MGT_KEY")


def _management_key() -> str | None:
    """The ZenMux management key, or None when it is configured nowhere.

    The process environment wins, but an EMPTY value counts as unset: this desk's shell
    exports empty ZENMUX_* variables, and an empty string is "set" to a plain
    `os.environ.get`, which would shadow the real key in `.env` (the same trap that
    once turned a configured API key into a 403). The `.env` fallback goes through
    `app.config.dotenv_path()`, the repo's single dotenv seam, so a test or an
    `OPEN_OTC_ENV_FILE=` override is honoured here exactly as it is everywhere else.
    """
    for name in KEY_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    backend = str(REPO_ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    try:
        from app.config import dotenv_path
        from dotenv import dotenv_values
    except ImportError:
        return None
    path = dotenv_path()
    if path is None or not path.exists():
        return None
    values = dotenv_values(path)
    for name in KEY_NAMES:
        value = (values.get(name) or "").strip()
        if value:
            return value
    return None


def _db_path() -> Path:
    url = os.environ.get("OPEN_OTC_DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        return Path(url[len("sqlite:///"):])
    return REPO_ROOT / "data" / "open_otc.sqlite3"


def _matches(run_id: int) -> list[dict]:
    con = sqlite3.connect(_db_path())
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select id, workflow_id, model_id, reasoning_effort, status, objective_score,"
        " score_breakdown, transcript_path from arena_match where run_id=?"
        " order by workflow_id, model_id", (run_id,)).fetchall()
    return [dict(r) for r in rows]


def _generation_ids(transcript_path: str | None) -> list[str]:
    if not transcript_path:
        return []
    main = REPO_ROOT / transcript_path
    trials = sorted(main.parent.glob("transcript.trial*.json"))
    ids: list[str] = []
    for path in trials or [main]:
        try:
            steps = json.loads(path.read_text()).get("steps") or []
        except (OSError, ValueError):
            continue
        for step in steps:
            for call in step.get("usage") or []:
                gid = call.get("generation_id")
                if gid and gid not in ids:
                    ids.append(gid)
    return ids


def _lookup(gid: str, key: str) -> dict:
    req = urllib.request.Request(BILLING_URL.format(gid),
                                 headers={"Authorization": f"Bearer {key}"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                body = json.loads(resp.read())
            data = body.get("data", body) if isinstance(body, dict) else {}
            rating = (data or {}).get("ratingResponses") or {}
            amount = rating.get("billAmount")
            if amount is None:
                return {"error": (body or {}).get("message") or "no billAmount"}
            return {"usd": float(amount)}
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if attempt == 2:
                return {"error": type(exc).__name__}
            time.sleep(2 * (attempt + 1))
    return {"error": "unreachable"}


def _billed(run_id: int, matches: list[dict]) -> dict[int, dict]:
    key = _management_key()
    if not key:
        sys.exit("--billed needs ZENMUX_MANAGEMENT_KEY (or the older ZENMUX_MGT_KEY) "
                 "in the environment or the repo's .env")
    cache_path = REPO_ROOT / "artifacts" / "arena" / str(run_id) / "billing.json"
    cache: dict[str, dict] = (json.loads(cache_path.read_text())
                              if cache_path.exists() else {})
    per_match = {m["id"]: _generation_ids(m["transcript_path"]) for m in matches}
    todo = sorted({g for ids in per_match.values() for g in ids
                   if "usd" not in cache.get(g, {})})
    with ThreadPoolExecutor(max_workers=8) as pool:
        for gid, res in zip(todo, pool.map(lambda g: _lookup(g, key), todo)):
            cache[gid] = res
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=1))
    out = {}
    for mid, ids in per_match.items():
        got = [cache[g]["usd"] for g in ids if "usd" in cache.get(g, {})]
        out[mid] = {"usd": round(sum(got), 6), "found": len(got), "ids": len(ids)}
    return out


def _usd(u: dict | None) -> str:
    if not u:
        return "—"
    if u.get("usd") is not None:
        return f"${u['usd']:.4f}"
    return f"${u.get('usd_low', 0):.4f}–{u.get('usd_high', 0):.4f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--billed", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    matches = _matches(args.run)
    billed = _billed(args.run, matches) if args.billed else {}
    rows = []
    for m in matches:
        bd = json.loads(m["score_breakdown"] or "{}")
        u = bd.get("usage")
        rows.append({
            "match": m["id"], "workflow": m["workflow_id"], "model": m["model_id"],
            "effort": m["reasoning_effort"] or None, "status": m["status"],
            "score": m["objective_score"], "usage": u, "billed": billed.get(m["id"]),
        })
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    hdr = (f"{'workflow':<34}{'model':<22}{'eff':<7}{'score':>6}{'calls':>6}"
           f"{'input':>11}{'cached':>11}{'output':>9}{'reason':>9}  {'list USD':<16}"
           + ("  billed USD" if args.billed else ""))
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        u = r["usage"] or {}
        line = (f"{r['workflow']:<34}{r['model']:<22}{(r['effort'] or '-'):<7}"
                f"{(r['score'] if r['score'] is not None else float('nan')):>6.1f}"
                f"{u.get('calls', 0):>6}{u.get('input', 0):>11,}{u.get('cache_read', 0):>11,}"
                f"{u.get('output', 0):>9,}{u.get('reasoning', 0):>9,}  {_usd(r['usage']):<16}")
        if args.billed:
            b = r["billed"] or {}
            line += f"  ${b.get('usd', 0):.4f} ({b.get('found', 0)}/{b.get('ids', 0)} ids)"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
