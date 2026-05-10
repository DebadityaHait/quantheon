"""Bounded session-booking identity verification from receipts and target rows."""
from __future__ import annotations

import json
import hashlib
from typing import Any


def position_fingerprint(position) -> str:
    def canonical(value):
        if isinstance(value, dict):
            return {key: canonical(item) for key, item in value.items()}
        if isinstance(value, list):
            return [canonical(item) for item in value]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return value
    fields = {"portfolio_id": position.portfolio_id, "product_id": position.product_id,
              "underlying": position.underlying, "currency": position.currency,
              "quantity": position.quantity, "entry_price": position.entry_price,
              "trade_effective_date": str(position.trade_effective_date),
              "terms": (dict((position.product.raw_terms or {}).get("terms") or {})
                        if position.product else dict(position.product_kwargs or {}))}
    return "sha256:" + hashlib.sha256(json.dumps(canonical(fields), sort_keys=True, default=str).encode()).hexdigest()


def verify_booking(session, *, workflow_id: int, portfolio_id: int,
                   position_id: int | None = None, expected_terms: dict | None = None,
                   underlying: str | None = None) -> dict[str, Any]:
    from app.models import Position, Portfolio, SessionArtifact
    from app.services.deep_agent.artifact_access import raw_artifact_content
    if session.get(Portfolio, portfolio_id) is None:
        raise ValueError("Target portfolio not found")
    if position_id is None and not underlying:
        return {"terminal": False, "verdict": "missing_trade_scope",
                "response": "Specify the position or underlying to identify the session booking."}
    receipts = []
    for row in session.query(SessionArtifact).filter_by(workflow_id=workflow_id, kind="tool_result").order_by(SessionArtifact.id).all():
        receipt = (row.payload or {}).get("operation_receipt") or {}
        if receipt.get("version") != "operation_receipt_v1" or receipt.get("kind") != "booking":
            continue
        if receipt.get("portfolio_id") != portfolio_id:
            continue
        if position_id is not None and receipt.get("position_id") != position_id:
            continue
        candidate = session.get(Position, receipt["position_id"])
        if underlying and candidate is not None and candidate.underlying != underlying:
            continue
        raw_artifact_content(row)  # canonical receipt must remain recoverable
        receipts.append((row, receipt))
    if not receipts:
        # A matching historical position is not evidence of a session booking.
        query = session.query(Position).filter(Position.portfolio_id == portfolio_id)
        if position_id is not None:
            query = query.filter(Position.id == position_id)
        if underlying:
            query = query.filter(Position.underlying == underlying)
        count = query.count()
        return {"terminal": True, "verdict": "no_session_booking", "portfolio_id": portfolio_id,
                "target_book_match_count": count, "booking_receipt": None,
                "response": f"No booking receipt exists for this trade in the current session. Portfolio {portfolio_id} contains {count} matching stored position(s); those rows cannot be confirmed as a new session booking. Nothing was changed."}
    pids = {r[1]["position_id"] for r in receipts}
    if len(pids) != 1:
        return {"terminal": False, "verdict": "ambiguous_booking", "candidate_position_ids": sorted(pids),
                "response": "Several session bookings match this scope; specify the position to verify."}
    artifact, receipt = receipts[-1]
    position = session.get(Position, receipt["position_id"])
    if position is None or position.portfolio_id != portfolio_id:
        return {"terminal": True, "verdict": "position_absent", "portfolio_id": portfolio_id,
                "response": f"The session booking receipt identifies position {receipt['position_id']}, but it is absent from portfolio {portfolio_id}. Nothing was changed."}
    terms = dict((position.product.raw_terms or {}).get("terms") or {}) if position.product else dict(position.product_kwargs or {})
    values = {**terms, "product_type": position.product_type,
              "underlying": position.underlying, "quantity": position.quantity,
              "currency": position.currency,
              "trade_effective_date": position.trade_effective_date.date().isoformat() if position.trade_effective_date else None}
    provenance = (position.source_payload or {}).get("build_provenance") or {}
    # A fixing is distinct from a native term; never synthesize it from strike.
    values["initial_price"] = terms.get("initial_price", provenance.get("supplied_inputs", {}).get("initial_price"))
    differences = {key: {"expected": expected, "stored": values.get(key)}
                   for key, expected in (expected_terms or {}).items()
                   if values.get(key) != expected}
    if receipt.get("position_fingerprint") != position_fingerprint(position):
        differences["booking_record"] = {"expected": receipt.get("position_fingerprint"), "stored": position_fingerprint(position)}
    if underlying and position.underlying != underlying:
        differences["underlying"] = {"expected": underlying, "stored": position.underlying}
    verdict = "mismatch" if differences else "confirmed"
    observed = {"product_type": position.product_type, "underlying": position.underlying,
                "quantity": position.quantity, "currency": position.currency,
                "trade_effective_date": values["trade_effective_date"],
                "terms": {key: value for key, value in terms.items() if key in
                          {"strike", "barrier", "barrier_type", "option_type", "exercise_date", "contract_multiplier", "rebate"}}}
    identity_status = ("The booking receipt and stored target-book row agree."
                       if "booking_record" not in differences
                       else "The booking receipt does not match the current stored target-book row.")
    if differences:
        response = (f"Position {position.id} is the session booking in portfolio {portfolio_id}. {identity_status} "
                    f"Requested fields differ: {', '.join(differences)}. Actual stored contract: "
                    f"{json.dumps(observed, default=str, sort_keys=True)}. Nothing was changed.")
    else:
        response = (f"Position {position.id} in portfolio {portfolio_id} is the {position.underlying} trade booked in this session. "
                    f"{identity_status} Stored contract: {json.dumps(observed, default=str, sort_keys=True)}. Nothing was changed.")
    return {"terminal": True, "verdict": verdict, "portfolio_id": portfolio_id, "position_id": position.id,
            "booking_receipt": {"kind": "artifact", "artifact_id": artifact.id,
                                "content_hash": artifact.payload.get("content_hash")},
            "differences": differences, "checked_fields": sorted(expected_terms or {}),
            "observed_position": observed, "response": response}
