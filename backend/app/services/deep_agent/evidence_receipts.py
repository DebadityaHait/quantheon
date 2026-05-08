"""Server-owned operation receipts stored with exact captured tool results."""
from __future__ import annotations

from typing import Any
import json
from app.services.audit_trail import AUDIT_CONTEXT_KEY
from .artifact_access import _active_config
from .cas_backend import _canonical_input_hash

VALIDATION_TOOLS = {"check_term_completeness", "build_product", "validate_rfq_terms"}
BOOKING_TOOLS = {"book_position", "book_rfq_to_position", "book_extracted_trade"}


def turn_scope(config: dict | None) -> dict[str, Any]:
    values = _active_config(config)
    audit = values.get(AUDIT_CONTEXT_KEY) or {}
    return {"thread_id": audit.get("thread_id") or values.get("parent_thread_id") or values.get("thread_id"),
            "user_message_id": audit.get("user_message_id"),
            "workflow_id": values.get("workflow_id") or audit.get("workflow_id")}


def operation_receipt(name: str | None, args: dict | None, result: Any,
                      config: dict | None, *, call_id: str) -> dict | None:
    if isinstance(result, list):
        for block in result:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                try:
                    value, _ = json.JSONDecoder().raw_decode(block["text"].lstrip())
                except ValueError:
                    continue
                if isinstance(value, dict):
                    result = value
                    break
    if not isinstance(result, dict) or result.get("error"):
        return None
    args = args or {}
    receipt = {"version": "operation_receipt_v1", **turn_scope(config),
               "tool_name": name, "tool_call_id": call_id,
               "input_hash": _canonical_input_hash(args)}
    if name in VALIDATION_TOOLS:
        family = result.get("quantark_class") or args.get("quantark_class") or args.get("family")
        if name == "validate_rfq_terms":
            terms = args.get("terms") or {}
            if not isinstance(terms, dict):
                return None
            product = terms.get("product") or {}
            family = product.get("quantark_class")
        if not family:
            return None
        verdict = result.get("complete", result.get("ok", result.get("valid")))
        if not isinstance(verdict, bool):
            return None
        receipt.update(kind="validation", quantark_class=family,
                       representation=result.get("representation") or ("raw_build_inputs" if name == "build_product" else "native_product_terms"),
                       valid=verdict, missing_required=result.get("missing_required", result.get("missing", result.get("missing_fields", []))))
        return receipt
    if name in BOOKING_TOOLS:
        position = result.get("position") or result.get("booking") or {}
        pid = position.get("id") or position.get("position_id") or result.get("position_id")
        if not pid or result.get("ok") is False or position.get("status") in {"failed", "blocked", "rejected"}:
            return None
        receipt.update(kind="booking", position_id=pid,
                       portfolio_id=args.get("portfolio_id") or position.get("portfolio_id"))
        from app import database
        from app.models import Position
        from app.services.domains.booking_verification import position_fingerprint
        with database.SessionLocal() as session:
            stored = session.get(Position, pid)
            if stored is not None:
                receipt.update(portfolio_id=stored.portfolio_id,
                               position_fingerprint=position_fingerprint(stored))
        return receipt
    if name == "verify_position_booking" and result.get("terminal") is True:
        receipt.update(kind="position_verification", portfolio_id=args.get("portfolio_id"),
                       underlying=args.get("underlying"), position_id=args.get("position_id"),
                       verdict=result.get("verdict"), response=result.get("response"))
        return receipt
    return None


def current_receipts(session, *, config: dict | None, kind: str) -> list[tuple[Any, dict]]:
    from app.models import SessionArtifact
    from .artifact_access import workflow_id_from_config
    scope = turn_scope(config)
    if scope["user_message_id"] is None:
        return []  # Without a server user-turn identity, only direct messages count.
    workflow = workflow_id_from_config(config)
    rows = session.query(SessionArtifact).filter_by(workflow_id=workflow, kind="tool_result").order_by(SessionArtifact.id).all()
    return [(row, receipt) for row in rows
            if (receipt := (row.payload or {}).get("operation_receipt"))
            and receipt.get("version") == "operation_receipt_v1"
            and receipt.get("kind") == kind
            and str(receipt.get("thread_id")) == str(scope["thread_id"])
            and receipt.get("user_message_id") == scope["user_message_id"]]
