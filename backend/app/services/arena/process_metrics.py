"""Raw evidence for the JDG judgment stat (spec 2026-10-06 §3, §5.1).

Pure: a trial's transcript steps + its workflow -> COUNTS. Scores are computed on
read in scoring.py, so the constants are versioned by ``SCHEME`` and never baked
into stored rows. Everything is step-scoped: a re-read in a LATER step is never
waste, because every ``task()`` delegation is a fresh persona without memory.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

#: v1.1 (2026-10-06 review): waste is classified ONCE per call (repeat OR dead, spec
#: §3.1) and record_answer is out of both numerator and denominator. v1 double-counted.
SCHEME = "jdg-v1.1"

FS_SEARCH = frozenset({"ls", "grep", "glob"})
#: Counted calls that are never "domain" calls (filesystem, compute, protocol).
NON_DOMAIN = FS_SEARCH | {"write_file", "edit_file", "delete", "execute",
                          "run_python", "record_answer", "write_todos"}
_EMPTY_PREFIXES = ("No matches found", "No files found")

#: Assertion types that name an ACCEPTED tool for the step.
POSITIVE_TOOL_TYPES = frozenset({
    "tool_called", "tool_result_path", "tools_routed_sequence", "own_result_read",
    "response_quotes_tool_value", "tool_result_ratio",
})
#: Assertion types that name a FORBIDDEN tool — never accepted.
NEGATIVE_TOOL_TYPES = frozenset({"tool_not_called"})
#: Assertion types that name no tool (``assertion_any_of`` is recursed into).
NON_TOOL_TYPES = frozenset({
    "assertion_any_of", "skill_routed", "skills_routed_sequence", "task_returned_id",
    "artifact_exists", "response_contains", "artifact_contains", "response_quotes_value",
    "answer_field_equals", "answer_field_quotes",
})


def _is_write(name: str) -> bool:
    from app.services.deep_agent.hitl import _RISK_LEVEL_BY_TOOL
    return _RISK_LEVEL_BY_TOOL.get(name) in {"write", "irreversible"}


def _as_dict(step: Any) -> Mapping:
    return step.model_dump() if hasattr(step, "model_dump") else step


def _canon(args: Any) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            return args
    return json.dumps(args, sort_keys=True, default=str)


def _result_text(content: Any) -> str:
    if isinstance(content, Mapping) and set(content) == {"raw"}:
        return str(content["raw"])
    return json.dumps(content, default=str) if content is not None else ""


def _names(node: Any, acc: set[str]) -> set[str]:
    """Collect accepted tool names from one assertion (dict or pydantic model)."""
    a = node.model_dump() if hasattr(node, "model_dump") else node
    if not isinstance(a, Mapping):
        return acc
    kind = a.get("type")
    if kind == "assertion_any_of":
        for branch in a.get("any_of") or []:
            _names(branch, acc)
    elif kind in POSITIVE_TOOL_TYPES:
        for key in ("name", "tool"):
            if isinstance(a.get(key), str):
                acc.add(a[key])
        # `names` (tools_routed_sequence); `via` (own_result_read: the read routes
        # that prove ownership, default read_artifact — an accepted way to read).
        for key in ("names", "via"):
            if isinstance(a.get(key), list):
                acc.update(x for x in a[key] if isinstance(x, str))
    return acc


def accepted_tools(step: Any) -> set[str]:
    """Tools a step accepts: expected_tools ∪ positive assertion tools (§3.2)."""
    acc: set[str] = set()
    for t in getattr(step, "expected_tools", None) or []:
        name = getattr(t, "name", None) if not isinstance(t, Mapping) else t.get("name")
        if isinstance(name, str):
            acc.add(name)
    for a in getattr(step, "assertions", None) or []:
        _names(a, acc)
    return acc


def _step_waste(calls: list[Mapping], results: dict[str, str]) -> tuple[int, int, int, int]:
    """(repeats, dead_searches, wasted, denominator) for one step.

    ``wasted`` classifies each call ONCE (repeat OR dead search — spec §3.1); the two
    components are kept as diagnostics and may overlap. ``record_answer`` is protocol,
    not work: it is in neither the numerator nor the denominator.
    """
    repeats = dead = wasted = denom = 0
    seen: set[tuple[str, str]] = set()
    context = ""
    for c in calls:
        name = c.get("name") or ""
        text = results.get(c.get("id"))
        if name == "record_answer":
            if text is not None:
                context += "\n" + text.lower()
            continue
        denom += 1
        key = (name, _canon(c.get("args")))
        is_repeat = False
        if _is_write(name):
            seen.clear()                     # state may have changed: re-reads are legit
        elif key in seen:
            is_repeat = True
        seen.add(key)
        is_dead = False
        if name in FS_SEARCH and text is not None:
            stripped = text.strip()
            args = c.get("args") if isinstance(c.get("args"), Mapping) else {}
            pattern = str(args.get("pattern") or "")
            if stripped in ("", "[]") or stripped.startswith(_EMPTY_PREFIXES):
                is_dead = True
            elif name == "grep" and pattern and pattern.lower() in context:
                is_dead = True
        repeats += is_repeat
        dead += is_dead
        wasted += is_repeat or is_dead
        if text is not None:
            context += "\n" + text.lower()
    return repeats, dead, wasted, denom


def process_record(steps: Iterable[Any], workflow: Any) -> dict:
    wf_steps = list(workflow.steps)
    repeats = dead = wasted = denom = 0
    scored = hits = 0
    trap_steps: list[int] = []
    trap_reads = trap_n = routine_reads = routine_n = 0
    matched = unmatched = 0
    for pos, raw in enumerate(steps):
        s = _as_dict(raw)
        idx = s.get("index", pos)
        calls = [c for c in (s.get("tool_calls") or []) if isinstance(c, Mapping)]
        results = {r.get("tool_call_id"): _result_text(r.get("content"))
                   for r in (s.get("tool_results") or []) if isinstance(r, Mapping)}
        r_, d_, w_, n_ = _step_waste(calls, results)
        repeats, dead, wasted, denom = repeats + r_, dead + d_, wasted + w_, denom + n_
        mstep = wf_steps[idx] if isinstance(idx, int) and 0 <= idx < len(wf_steps) else None
        if mstep is None or mstep.user != s.get("user"):
            unmatched += 1
            continue
        matched += 1
        domain = [c for c in calls if (c.get("name") or "") not in NON_DOMAIN]
        accepted = accepted_tools(mstep)
        if accepted and domain:
            scored += 1
            hits += domain[0].get("name") in accepted
        reads = sum(1 for c in domain if not _is_write(c.get("name") or ""))
        if getattr(mstep, "trap", False):
            trap_steps.append(idx)
            trap_reads += reads
            trap_n += 1
        else:
            routine_reads += reads
            routine_n += 1
    return {
        "scheme": SCHEME,
        "manifest_version": getattr(workflow, "manifest_version", None),
        "waste": {"repeats": repeats, "dead_searches": dead, "wasted": wasted,
                  "denominator": denom},
        "selection": {"scored_steps": scored, "hits": hits},
        "calibration": {"trap_steps": trap_steps, "trap_reads": trap_reads, "trap_n": trap_n,
                        "routine_reads": routine_reads, "routine_n": routine_n},
        "matched_steps": matched, "unmatched_steps": unmatched,
    }


def safe_process_record(steps: Iterable[Any], workflow: Any) -> dict:
    """process_record that never raises — a metrics bug must never fail a match."""
    try:
        return process_record(steps, workflow)
    except Exception as exc:  # noqa: BLE001
        return {"unavailable": f"{type(exc).__name__}: {exc}"}


def _record_for(steps: list | None, workflow: Any, missing_reason: str) -> dict:
    if steps is None:
        return {"unavailable": missing_reason}
    return safe_process_record(steps, workflow)


def map_trial_transcripts(stored_counts: list, candidate_counts: list[int]) -> list:
    """Map each stored trial to the unique transcript file with its tool-call count.

    ``aggregate`` keeps only clean trials, so position i is not file i. A count shared
    by two candidates (or two trials) is ambiguous -> None, never a guess.
    """
    # Exactly as many files as clean trials, and every position agrees: no trial
    # was skipped, so position IS identity — this also resolves tied counts.
    if len(candidate_counts) == len(stored_counts) and all(
            c is not None and c == v for c, v in zip(stored_counts, candidate_counts)):
        return list(range(len(stored_counts)))
    out: list = []
    for c in stored_counts:
        hits = [k for k, v in enumerate(candidate_counts) if c is not None and v == c]
        same = sum(1 for x in stored_counts if x is not None and x == c)
        out.append(hits[0] if len(hits) == 1 and same == 1 else None)
    return out


def _has_record(holder: dict) -> bool:
    """A real (scheme-bearing) record is frozen; an `unavailable` one may be retried
    — e.g. a first run that resolved transcripts against the wrong checkout."""
    proc = holder.get("process")
    # Only a CURRENT-scheme record is frozen; an older scheme (v1 double-counted
    # waste) or an `unavailable` marker is replaced on the next backfill.
    return isinstance(proc, dict) and proc.get("scheme") == SCHEME


def backfill_breakdown(bd: dict, trial_steps: list, workflow: Any,
                       missing_reason: str = "transcript_missing") -> tuple[dict | None, str]:
    """Return a copy of ``bd`` with ``process`` added per trial, or (None, reason).

    Adds exactly one key per trial and never touches another; skips (writes
    nothing) on an already-backfilled or structurally malformed row.
    """
    import copy

    trials = bd.get("aggregate")
    if isinstance(trials, list) and trials:
        n = bd.get("n_trials")
        if (isinstance(n, int) and n != len(trials)) or len(trial_steps) != len(trials) \
                or not all(isinstance(t, dict) for t in trials):
            return None, "malformed_aggregate"
        if all(_has_record(t) for t in trials):
            return None, "already_present"
        new = copy.deepcopy(bd)
        for t, steps in zip(new["aggregate"], trial_steps):
            if not _has_record(t):
                t["process"] = _record_for(steps, workflow, missing_reason)
        return new, "ok"
    if isinstance(bd.get("n_trials"), int) and bd["n_trials"] > 1:
        return None, "malformed_aggregate"
    if _has_record(bd):
        return None, "already_present"
    new = copy.deepcopy(bd)
    new["process"] = _record_for(trial_steps[0] if trial_steps else None, workflow,
                                 missing_reason)
    return new, "ok"
