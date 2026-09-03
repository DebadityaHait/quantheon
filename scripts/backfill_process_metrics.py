#!/usr/bin/env python
"""Add JDG `process` evidence to historical arena matches (spec 2026-10-06 §5.5).

Dry run by default. Adds one key per trial and NOTHING else; every card's OVR,
stats, CON, position and SBJ is derived before and after and must be identical,
or the script refuses to write. Transcripts are read from disk next to each row's
transcript_path; a missing one is recorded as {"unavailable": "transcript_missing"}.

    PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --all
    PYTHONPATH=backend .venv/bin/python scripts/backfill_process_metrics.py --run 145 --write
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_CORE = ("ovr", "base_ovr", "con", "stats", "position", "sbj")


def _trial_steps(transcript_path: str | None, stored_counts: list, loaded,
                 repo_root: Path = REPO) -> list:
    """Steps for each stored trial, matched to transcript files by tool-call count."""
    from app.golden_workflows.transcript import MatchTranscript
    from app.services.arena import process_metrics as pm
    from app.services.arena.scoring import diagnose_heuristic

    if not transcript_path:
        return [None] * len(stored_counts)
    base = Path(transcript_path)
    # A relative transcript_path is relative to the checkout the APP ran in (where
    # artifacts/ lives) — not necessarily this script's checkout (e.g. a worktree).
    base = base if base.is_absolute() else Path(repo_root) / base
    files = sorted(base.parent.glob("transcript.trial*.json"),
                   key=lambda p: int(p.stem.removeprefix("transcript.trial") or 0))
    if not files and base.exists():
        files = [base]
    candidates, counts = [], []
    for f in files:
        try:
            t = MatchTranscript.model_validate(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
        candidates.append(t)
        counts.append(diagnose_heuristic(t, loaded)["tool_calls"])
    mapping = pm.map_trial_transcripts(stored_counts, counts)
    return [[s.model_dump() for s in candidates[k].steps] if k is not None else None
            for k in mapping]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--run", type=int)
    scope.add_argument("--all", action="store_true")
    ap.add_argument("--write", action="store_true", help="persist (default: dry run)")
    ap.add_argument("--repo-root", type=Path, default=REPO,
                    help="checkout that relative transcript paths resolve against "
                         "(the one the app ran in; default: this script's checkout)")
    args = ap.parse_args()

    from app.database import SessionLocal, init_db
    from app.golden_workflows.registry import get_workflow_bundle
    from app.models import ArenaMatch
    from app.services.arena import process_metrics as pm
    from app.services.arena.store import _match_card

    init_db()
    tally: Counter = Counter()
    changed_cards = []
    with SessionLocal() as s:
        q = s.query(ArenaMatch).filter(ArenaMatch.status == "scored")
        if args.run is not None:
            q = q.filter(ArenaMatch.run_id == args.run)
        for m in q.all():
            bd = m.score_breakdown or {}
            try:
                loaded = get_workflow_bundle(m.workflow_id)
            except Exception:  # noqa: BLE001
                tally["workflow_unavailable"] += 1
                continue
            trials = bd["aggregate"] if isinstance(bd.get("aggregate"), list) and bd["aggregate"] else [bd]
            stored = [((t.get("diagnosis") or {}).get("counts_detail") or {}).get("tool_calls")
                      if isinstance(t, dict) else None for t in trials]
            if (m.config or {}).get("merged_from"):
                # A merge folds trials from SEVERAL runs; this row's transcript dir
                # belongs to one of them, so no file can be trusted for any trial.
                new, why = pm.backfill_breakdown(bd, [None] * len(trials), loaded.workflow,
                                                 missing_reason="merged_run")
            else:
                new, why = pm.backfill_breakdown(
                    bd, _trial_steps(m.transcript_path, stored, loaded, args.repo_root),
                    loaded.workflow)
            tally[why] += 1
            if new is None:
                continue
            frozen = (m.config or {}).get("provenance")
            before, _ = _match_card(bd, m.workflow_id, frozen=frozen)
            after, _ = _match_card(new, m.workflow_id, frozen=frozen)
            if any((before or {}).get(k) != (after or {}).get(k) for k in _CORE):
                changed_cards.append(m.id)
                continue
            if args.write:
                m.score_breakdown = new
        if changed_cards:
            print(f"REFUSING: card core would change for matches {changed_cards}", file=sys.stderr)
            s.rollback()
            return 1
        if args.write:
            s.commit()
    print(("WROTE " if args.write else "DRY RUN ") + json.dumps(dict(tally), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
