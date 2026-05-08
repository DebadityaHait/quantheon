"""Finish narrow booking-confirmation turns once exact evidence is conclusive."""
import re
from langchain.agents.middleware.types import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage


def confirmation_only(text: str) -> bool:
    return bool(re.search(r"confirm|verify|check|show", text, re.I)
                and re.search(r"position|booked|booking", text, re.I)
                and not re.search(r"price|reprice|risk|delta|greek|ticket|report|audit|approve|book (?:it|this|that|a|the)", text, re.I))


class PositionVerificationMiddleware(AgentMiddleware):
    def _response(self, request):
        from app import database
        from app.models import AgentMessage
        from .evidence_receipts import turn_scope, current_receipts
        from .artifact_access import raw_artifact_content
        config = getattr(getattr(request, "runtime", None), "config", None)
        scope = turn_scope(config)
        if scope["user_message_id"] is None:
            return None
        with database.SessionLocal() as session:
            user = session.get(AgentMessage, scope["user_message_id"])
            if user is None or str(user.thread_id) != str(scope["thread_id"]) or not confirmation_only(user.content):
                return None
            receipts = current_receipts(session, config=config, kind="position_verification")
            if not receipts:
                return None
            artifact, receipt = receipts[-1]
            # A specific position named by the user cannot be replaced with a
            # terminal check of another position in the same turn.
            named = re.search(r"position\s*(?:id\s*)?#?\s*(\d+)\b", user.content, re.I)
            if named and receipt.get("position_id") != int(named.group(1)):
                return None
            raw_artifact_content(artifact)
            return ModelResponse(result=[AIMessage(content=receipt["response"])])

    def wrap_model_call(self, request, handler):
        response = self._response(request)
        return response if response is not None else handler(request)

    async def awrap_model_call(self, request, handler):
        response = self._response(request)
        return response if response is not None else await handler(request)
