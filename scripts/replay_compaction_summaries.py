#!/usr/bin/env python
"""Replay recorded summary responses with the current renderer; no live calls.

Read-only indexed trace queries. Selection/content are held fixed: the model is
not asked for a second chance. Full raw trace remains in the trace database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from app.config import Settings
from app.services.deep_agent.compaction import (
    LedgerScopedCompactionMiddleware, _REQUEST_STATE, _text_tokens,
)


def replay(trace_db: Path, thread_id: int) -> dict:
    connection = sqlite3.connect(f"file:{trace_db.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    middleware = LedgerScopedCompactionMiddleware(GenericFakeChatModel(messages=iter([])),
                                                 backend=None, settings=Settings())
    cases = []
    try:
        for span in connection.execute(
            "select id,parent_run_id,inputs,outputs,extra from trace_runs "
            "where thread_id=? and run_type='llm' order by start_time", (thread_id,),
        ):
            if json.loads(span["extra"] or "{}").get("metadata", {}).get("lc_source") != "summarization":
                continue
            case = {"span_id": span["id"], "accepted": False}
            try:
                prompt = json.loads(span["inputs"])["prompts"][0]
                cards = json.loads(prompt.split("<reference_catalog>\n", 1)[1].split("\n</reference_catalog>", 1)[0])
                if any(c.get("kind") == "artifact" and "reference" not in c for c in cards):
                    raise ValueError("Replay needs the original full recorded catalog")
                catalog = {card["key"]: card for card in cards}
                generation = json.loads(span["outputs"])["generations"][0][0]
                kwargs = generation["message"]["kwargs"]
                raw = generation["text"].strip().removeprefix("```json").removesuffix("```").strip()
                selected = json.loads(raw)["retained_reference_keys"]
                case["response_sha256"] = hashlib.sha256(span["outputs"].encode()).hexdigest()
                state = {}
                parent = span["parent_run_id"]
                for _ in range(5):
                    ancestor = connection.execute(
                        "select name,parent_run_id,inputs from trace_runs where id=?", (parent,),
                    ).fetchone()
                    if not ancestor:
                        break
                    if ancestor["name"] == "model":
                        snapshot = json.loads(ancestor["inputs"])
                        state = {"todos": snapshot.get("todos", []), "messages": [
                            HumanMessage(**m["kwargs"]) for m in snapshot.get("messages", [])
                            if m.get("id", [])[-1:] == ["HumanMessage"]
                        ]}
                        break
                    parent = ancestor["parent_run_id"]
                token = _REQUEST_STATE.set(state)
                try:
                    result = middleware._validated_summary(AIMessage(**kwargs), catalog)
                    message = middleware._build_new_messages_with_path(result, "/conversation_history/replay.md")[0]
                finally:
                    _REQUEST_STATE.reset(token)
                actual = [card["key"] for card in result.references]
                required = [c["key"] for c in cards if c.get("required")]
                if set(actual) != set(selected) | set(required):
                    raise ValueError("Reference selection changed during replay")
                case.update(accepted=True, retained_tokens=_text_tokens(message.text),
                            selected_keys=actual, references_preserved=True)
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                case["error"] = str(exc)
            cases.append(case)
    finally:
        connection.close()
    return {"thread_id": thread_id, "cases": cases, "n": len(cases),
            "accepted": sum(c["accepted"] for c in cases),
            "max_retained_tokens": max((c.get("retained_tokens", 0) for c in cases), default=0),
            "budgets": {"retained": middleware.retained_tokens, "references": middleware.reference_tokens},
            "method": "fixed recorded response and selection; renderer/checkpoint wrapper replay; no live model calls"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-db", type=Path, default=Path("data/agent_traces.sqlite3"))
    parser.add_argument("--thread", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.trace_db, args.thread)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}))
    return 0 if result["n"] > 0 and result["accepted"] == result["n"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
