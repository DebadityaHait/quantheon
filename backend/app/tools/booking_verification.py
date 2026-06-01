"""Exact, scoped position confirmation; no business mutations."""
from typing import Any
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from app import database
from app.services.deep_agent.capability_gate import capability_gated
from app.services.deep_agent.envelopes import ToolGroup
from app.services.deep_agent.artifact_access import workflow_id_from_config
from app.services.domains.booking_verification import verify_booking


class VerifyPositionBookingInput(BaseModel):
    portfolio_id: int
    position_id: int | None = None
    underlying: str | None = None
    expected_terms: dict[str, Any] = Field(default_factory=dict, description="Only fields the user asked to verify; leave empty for booking identity. Never add raw missing-term requirements.")


@capability_gated(group=ToolGroup.DOMAIN_READ)
@tool("verify_position_booking", args_schema=VerifyPositionBookingInput)
def verify_position_booking_tool(portfolio_id: int, position_id: int | None = None,
                                 underlying: str | None = None, expected_terms: dict | None = None,
                                 config: RunnableConfig = None) -> dict:
    """Confirm a session booking using its scoped receipt and target-book row.
    Prefer this for 'confirm the position we just booked'. terminal=true ends
    verification: report the verdict; no repeated completeness/other-book audit.
    terminal=false identifies the specific ambiguity to resolve."""
    workflow = workflow_id_from_config(config)
    with database.SessionLocal() as session:
        return verify_booking(session, workflow_id=workflow, portfolio_id=portfolio_id,
                              position_id=position_id, underlying=underlying, expected_terms=expected_terms)
