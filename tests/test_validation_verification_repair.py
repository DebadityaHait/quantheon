from __future__ import annotations

from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.models import AgentThread, AgentMessage, Portfolio, PortfolioKind, SessionArtifact
from app.services.deep_agent.workflow_state import ensure_thread_workflow_state
from app.services.deep_agent.cas_backend import ContentAddressedFilesystemBackend
from app.services.deep_agent.term_grounding import TermGroundingMiddleware
from app.services.domains.product_builders import build_product
from app.tools.term_completeness import check_term_completeness

RAW = {"initial_price": 401.1, "strike": 401.1, "barrier": 320.88,
       "barrier_type": "DOWN_IN", "option_type": "PUT", "exercise_date": "2099-07-16",
       "rebate": 0, "contract_multiplier": 1}


def check(terms, representation):
    return check_term_completeness.invoke({"quantark_class": "BarrierOption", "terms": terms,
                                           "representation": representation})


def setup_scope(session):
    thread = AgentThread(title="verify", character="auto")
    session.add(thread); session.flush()
    state = ensure_thread_workflow_state(session, thread.id)
    user = AgentMessage(thread_id=thread.id, role="user", content="Confirm the position we just booked.")
    session.add(user); session.commit()
    config = {"configurable": {"thread_id": str(thread.id), "workflow_id": state.meta_workflow_id,
                               "session_id": state.router_session_id,
                               "__audit_context__": {"thread_id": thread.id, "user_message_id": user.id}}}
    return thread, user, config


def capture(config, name, args, result, call="c"):
    return ContentAddressedFilesystemBackend().capture_tool_result(
        tool_call_id=call, tool_name=name, content=json.dumps(result), tool_args=args,
        config=config, classification="domain_read")


def test_barrier_native_validation_has_no_false_initial_price_gap():
    built = build_product("BarrierOption", RAW, underlying="MSFT", currency="USD")
    assert check(RAW, "raw_build_inputs")["complete"]
    assert "initial_price" not in built.product_kwargs
    assert check(built.product_kwargs, "native_product_terms")["complete"]
    assert not check({**built.product_kwargs, "initial_price": 401.1}, "native_product_terms")["complete"]
    from app.tools._product_inputs import ToolRFQDraft
    from app.services.rfq import validate_rfq_terms
    draft = ToolRFQDraft(product=asdict(built.product_spec), quote_mode="price")
    assert validate_rfq_terms(draft.to_rfq_request_draft(), "price")["valid"]
    assert draft.to_rfq_request_draft().product["source_payload"]["build_provenance"]["supplied_inputs"]["initial_price"] == 401.1


@pytest.mark.parametrize("drop", ["strike", "barrier", "exercise_date"])
def test_native_missing_terms_remain_invalid(drop):
    terms = build_product("BarrierOption", RAW).product_kwargs
    terms.pop(drop)
    result = check(terms, "native_product_terms")
    assert not result["complete"]
    assert result["missing_required"] or result["errors"]


def test_market_checks_are_explicit_and_do_not_fill_defaults():
    result = check({"spot": 401.1}, "valuation_market")
    assert not result["complete"] and "valuation_date" in result["missing_required"]
    full = {"spot": 401.1, "rate": .04, "dividend_yield": .01, "volatility": .28, "valuation_date": "2026-07-16"}
    assert check(full, "valuation_market")["complete"]
    assert not check({**full, "spot": float("nan")}, "valuation_market")["complete"]


def test_fixing_reference_is_exact_scoped_and_outside_kwargs(session):
    from app.tools.products import build_product_tool
    _, _, config = setup_scope(session)
    ref = capture(config, "fetch_market_snapshot", {}, {"symbol": "MSFT", "source_metadata": {"fallback": False},
                  "data": {"rows": [{"date": "2026-07-16", "close": 401.1}]}}, "snapshot")
    args = {"family": "BarrierOption", "terms": RAW, "underlying": "MSFT", "currency": "USD",
            "fixing_references": [{"artifact_id": ref["artifact_id"], "fixing_date": "2026-07-16"}]}
    result = build_product_tool.invoke(args, config=config)
    assert result["ok"]
    prov = result["product_spec"]["source_payload"]["build_provenance"]
    assert prov["fixing_references"][0]["content_hash"] == ref["content_hash"]
    assert "fixing_references" not in result["product_kwargs"]
    from app.services.domains.build_provenance import validate_source_payload
    capture(config, "build_product", args, result, "captured-build")
    source = result["product_spec"]["source_payload"]
    edited_market = {"build_provenance": {
        **prov, "valuation_market": {"spot": 999, "currency": "CNY"},
        "market_origin": "explicit",
    }}
    assert validate_source_payload(edited_market, config=config, underlying="MSFT",
                                   terms=result["product_kwargs"], family="BarrierOption") == source
    changed_fixing = json.loads(json.dumps(source))
    changed_fixing["build_provenance"]["fixing_references"][0]["artifact_id"] += 1
    with pytest.raises(ValueError, match="captured product build"):
        validate_source_payload(changed_fixing, config=config, underlying="MSFT",
                                terms=result["product_kwargs"], family="BarrierOption")
    with pytest.raises(ValueError, match="date/close"):
        build_product_tool.invoke({**args, "terms": {**RAW, "initial_price": 402}}, config=config)
    wrong = {"configurable": {**config["configurable"], "workflow_id": 999999}}
    with pytest.raises(ValueError, match="current workflow"):
        build_product_tool.invoke(args, config=wrong)


def test_unsupported_family_is_rejected_before_fixing_lookup(session):
    from app.tools.products import build_product_tool
    _, _, config = setup_scope(session)
    result = build_product_tool.invoke({
        "family": "CliquetRatchetOption",
        "terms": {},
        "underlying": "MSFT",
        "fixing_references": [{"artifact_id": 999999999, "fixing_date": "2026-07-16"}],
    }, config=config)
    assert not result["ok"]
    assert any("unsupported_family" in warning for warning in result["warnings"])


def test_persona_validation_receipt_grounds_only_current_family_and_turn(session):
    _, user, config = setup_scope(session)
    terms = build_product("BarrierOption", RAW).product_kwargs
    args = {"quantark_class": "BarrierOption", "terms": terms, "representation": "native_product_terms"}
    result = check(terms, "native_product_terms")
    capture(config, "check_term_completeness", args, result)
    state = {"messages": [HumanMessage(content="validate"), ToolMessage(name="task", tool_call_id="t", content="persona checked"),
                           AIMessage(content="BarrierOption terms are not complete: missing required fields.")]}
    middleware = TermGroundingMiddleware()
    assert middleware.after_model(state, None, config) is None
    other = {"messages": [HumanMessage(content="validate"), AIMessage(content="AsianOption is not complete.")]}
    assert middleware.after_model(other, None, config) is not None
    stale = {"configurable": {**config["configurable"], "__audit_context__": {"thread_id": user.thread_id, "user_message_id": user.id + 1}}}
    assert middleware.after_model(state, None, stale) is not None


def test_failed_tool_does_not_mint_validation_receipt(session):
    _, _, config = setup_scope(session)
    ref = capture(config, "check_term_completeness", {"quantark_class": "BarrierOption"}, {"error": "unavailable"})
    session.expire_all()
    assert not session.get(SessionArtifact, ref["artifact_id"]).payload.get("operation_receipt")


def test_raw_receipt_cannot_ground_explicit_native_verdict(session):
    _, _, config = setup_scope(session)
    capture(config, "check_term_completeness", {"quantark_class": "BarrierOption", "terms": RAW},
            check(RAW, "raw_build_inputs"))
    state = {"messages": [HumanMessage(content="check"),
                          AIMessage(content="BarrierOption native_product_terms is not complete.")]}
    assert TermGroundingMiddleware().after_model(state, None, config) is not None


def test_pricing_task_reference_uses_task_run_not_agent_task(session, monkeypatch):
    from app.tools.risk import run_batch_pricing_tool
    from app.models import TaskRun
    from app.services.deep_agent.artifact_access import read_saved_record
    _, _, config = setup_scope(session)
    task = TaskRun(kind="batch_pricing", status="completed", result_payload={"risk_run_id": 123})
    session.add(task); session.commit()
    monkeypatch.setattr("app.services.domains.risk.run", lambda **kwargs: {"task_id": task.id, "status": "completed"})
    result = run_batch_pricing_tool.invoke({"portfolio_id": 1}, config=config)
    assert result["record_reference"]["kind"] == "task_run"
    capture(config, "run_batch_pricing", {"portfolio_id": 1}, result)
    session.expire_all()
    record = read_saved_record(session, workflow_id=config["configurable"]["workflow_id"],
                               kind="task_run", record_id=task.id, json_pointer="/result_payload")
    assert "123" in record["content"]
    with pytest.raises(ValueError):
        read_saved_record(session, workflow_id=config["configurable"]["workflow_id"], kind="task", record_id=task.id)


def test_fixing_dependency_remains_selectable_beyond_recent_catalog(session):
    from app.services.deep_agent.compaction import _REQUEST_CONFIG, _scoped_catalog
    from app.tools.products import build_product_tool
    _, _, config = setup_scope(session)
    snapshot = capture(config, "fetch_market_snapshot", {}, {"symbol": "MSFT", "source_metadata": {"fallback": False},
                       "data": {"rows": [{"date": "2026-07-16", "close": 401.1}]}}, "fixing")
    result = build_product_tool.invoke({"family": "BarrierOption", "terms": RAW, "underlying": "MSFT",
                 "fixing_references": [{"artifact_id": snapshot["artifact_id"], "fixing_date": "2026-07-16"}]}, config=config)
    for i in range(25):
        capture(config, "get_positions", {}, {"positions": []}, f"later{i}")
    capture(config, "build_product", {"family": "BarrierOption", "terms": RAW}, result, "built")
    token = _REQUEST_CONFIG.set(config)
    try:
        catalog = _scoped_catalog()
        assert f"artifact:{snapshot['artifact_id']}" in catalog
        from app.services.deep_agent.compaction import LedgerScopedCompactionMiddleware
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        m = LedgerScopedCompactionMiddleware(GenericFakeChatModel(messages=iter([])), backend=None)
        built_key = next(k for k, c in catalog.items() if c.get("reference", {}).get("tool_name") == "build_product")
        selected = m._validated_summary(AIMessage(content=json.dumps({"summary": "Continue booking.", "retained_reference_keys": [built_key]})), catalog)
        assert f"artifact:{snapshot['artifact_id']}" in [r["key"] for r in selected.references]
    finally:
        _REQUEST_CONFIG.reset(token)


def book(session, portfolio, spec):
    from app.services.domains.booking import BookingRequest, ProductBookingSpec, book_position
    position = book_position(session, BookingRequest(portfolio_id=portfolio.id,
                            product=ProductBookingSpec(**asdict(spec)), quantity=1))
    session.commit()
    return position


def test_booking_provenance_survives_product_reuse_per_position(session):
    portfolio = Portfolio(name="Book", base_currency="USD", kind=PortfolioKind.CONTAINER.value)
    session.add(portfolio); session.commit()
    a = build_product("BarrierOption", RAW, underlying="MSFT", currency="USD").product_spec
    first = book(session, portfolio, a)
    b = build_product("BarrierOption", {**RAW, "initial_price": 402}, underlying="MSFT", currency="USD").product_spec
    second = book(session, portfolio, b)
    assert first.product_id == second.product_id
    assert first.source_payload["build_provenance"]["supplied_inputs"]["initial_price"] == 401.1
    assert second.source_payload["build_provenance"]["supplied_inputs"]["initial_price"] == 402
    assert "initial_price" not in second.product_kwargs


def test_option_core_currency_mirror_uses_booked_position_currency(session):
    from app.models import OptionCoreTerm
    from app.services.domains.position_terms import upsert_position_term_rows
    portfolio = Portfolio(name="USD Book", base_currency="USD", kind=PortfolioKind.CONTAINER.value)
    session.add(portfolio); session.commit()
    position = book(session, portfolio, build_product("BarrierOption", RAW,
                    underlying="MSFT", currency="USD").product_spec)
    upsert_position_term_rows(session, position)
    session.flush()
    assert position.currency == "USD"
    assert session.get(OptionCoreTerm, position.id).currency == "USD"


def test_verification_confirms_receipt_and_target_and_stops_model(session):
    from app.services.domains.booking_verification import verify_booking
    from app.services.deep_agent.position_verification import PositionVerificationMiddleware
    _, _, config = setup_scope(session)
    portfolio = Portfolio(name="Book", base_currency="USD", kind=PortfolioKind.CONTAINER.value)
    session.add(portfolio); session.commit()
    position = book(session, portfolio, build_product("BarrierOption", RAW, underlying="MSFT", currency="USD").product_spec)
    capture(config, "book_position", {"portfolio_id": portfolio.id}, {"ok": True, "position": {"id": position.id}}, "booking")
    args = {"portfolio_id": portfolio.id, "position_id": position.id}
    result = verify_booking(session, workflow_id=config["configurable"]["workflow_id"], **args,
                            expected_terms={"strike": 401.1, "initial_price": 401.1,
                                            "product_type": "BarrierOption"})
    assert result["terminal"] and result["verdict"] == "confirmed", result
    assert result["observed_position"]["product_type"] == "BarrierOption"
    assert "DOWN_IN" in result["response"]
    capture(config, "verify_position_booking", args, result, "verify")
    request = SimpleNamespace(runtime=SimpleNamespace(config=config))
    def unexpected(_):
        raise AssertionError("conclusive verification must not make another model call")
    response = PositionVerificationMiddleware().wrap_model_call(request, unexpected)
    assert str(position.id) in response.result[0].content
    mismatch = verify_booking(session, workflow_id=config["configurable"]["workflow_id"], **args, expected_terms={"strike": 999})
    assert mismatch["terminal"] and mismatch["verdict"] == "mismatch"
    assert "DOWN_IN" in mismatch["response"]
    capture(config, "verify_position_booking", args, mismatch, "verify-mismatch")
    response = PositionVerificationMiddleware().wrap_model_call(request, unexpected)
    assert "DOWN_IN" in response.result[0].content


def test_old_matching_trade_is_not_a_session_booking(session):
    from app.services.domains.booking_verification import verify_booking
    _, _, config = setup_scope(session)
    portfolio = Portfolio(name="Book", base_currency="USD", kind=PortfolioKind.CONTAINER.value)
    session.add(portfolio); session.commit()
    position = book(session, portfolio, build_product("BarrierOption", RAW, underlying="MSFT").product_spec)
    result = verify_booking(session, workflow_id=config["configurable"]["workflow_id"], portfolio_id=portfolio.id,
                            position_id=position.id, underlying="MSFT")
    assert result["terminal"] and result["verdict"] == "no_session_booking"
    assert result["target_book_match_count"] == 1


def test_compound_request_is_not_short_circuited():
    from app.services.deep_agent.position_verification import confirmation_only
    assert confirmation_only("Show the booked position and confirm it's the barrier.")
    assert not confirmation_only("Confirm the booked position and price the book")
    assert not confirmation_only("Book this position now")


def test_errored_tool_message_cannot_mint_receipt_even_if_json_looks_valid(session):
    from app.services.deep_agent.ground_truth import GroundTruthArtifactMiddleware
    _, _, config = setup_scope(session)
    args = {"quantark_class": "BarrierOption", "terms": RAW}
    request = SimpleNamespace(tool_call={"name": "check_term_completeness", "id": "err", "args": args},
                              runtime=SimpleNamespace(config=config))
    result = GroundTruthArtifactMiddleware(tools=[check_term_completeness]).wrap_tool_call(
        request, lambda _: ToolMessage(content=json.dumps({"quantark_class": "BarrierOption", "complete": True}),
                                      status="error", name="check_term_completeness", tool_call_id="err"))
    session.expire_all()
    artifact = session.get(SessionArtifact, result.additional_kwargs["artifact_ref"]["artifact_id"])
    assert artifact.payload["operation_receipt"] is None


def test_list_content_blocks_receive_same_server_receipt(session):
    _, _, config = setup_scope(session)
    ref = capture(config, "check_term_completeness", {"quantark_class": "BarrierOption", "representation": "native_product_terms"},
                  [{"type": "text", "text": json.dumps({"quantark_class": "BarrierOption", "representation": "native_product_terms", "complete": True})}])
    session.expire_all()
    assert session.get(SessionArtifact, ref["artifact_id"]).payload["operation_receipt"]["representation"] == "native_product_terms"


def test_new_tool_is_reachable_in_all_personas():
    from app.tools import QUANT_AGENT_TOOLS
    from app.services.agents import DEEP_AGENT_TOOL_NAMES
    from app.services.deep_agent.hitl import _RISK_LEVEL_BY_TOOL, _LABEL_BY_TOOL
    assert "verify_position_booking" in {t.name for t in QUANT_AGENT_TOOLS}
    assert "verify_position_booking" in DEEP_AGENT_TOOL_NAMES
    assert _RISK_LEVEL_BY_TOOL["verify_position_booking"] == "read"
    assert _LABEL_BY_TOOL["verify_position_booking"]


def test_copied_provenance_requires_exact_build_and_rejects_attribution(session):
    from app.services.domains.build_provenance import validate_source_payload
    _, _, config = setup_scope(session)
    built = build_product("BarrierOption", RAW, underlying="MSFT", currency="USD")
    source = built.product_spec.source_payload
    with pytest.raises(ValueError, match="captured product build"):
        validate_source_payload(source, config=config, underlying="MSFT", terms=built.product_kwargs)
    capture(config, "build_product", {"family": "BarrierOption", "terms": RAW},
            {"ok": True, "product_spec": asdict(built.product_spec), "quantark_class": "BarrierOption"}, "build")
    assert validate_source_payload(source, config=config, underlying="MSFT", terms=built.product_kwargs) == source
    edited_market = {"build_provenance": {
        **source["build_provenance"],
        "valuation_market": {"spot": 999, "currency": "CNY", "asset_name": "edited"},
        "market_origin": "explicit",
    }}
    assert validate_source_payload(edited_market, config=config, underlying="MSFT",
                                   terms=built.product_kwargs) == source
    with pytest.raises(ValueError, match="attribution"):
        validate_source_payload({**source, "actor": "approved"}, config=config, underlying="MSFT")
    with pytest.raises(ValueError, match="captured product build"):
        validate_source_payload(source, config=config, underlying="MSFT",
                                terms={**built.product_kwargs, "strike": 999})


def test_rfq_adapter_infers_blank_currency_from_underlying():
    from app.tools._product_inputs import ToolRFQDraft, rfq_draft_to_product_payload
    draft = ToolRFQDraft.model_validate({
        "product": {"underlying": "000300.SH", "currency": "", "quantark_class": "BarrierOption"},
        "market": {"currency": ""},
    }).to_rfq_request_draft()
    assert draft.market.currency == "CNY"
    assert draft.product["currency"] == "CNY"
    product_payload = rfq_draft_to_product_payload({
        "underlying": "000300.SH", "market": {"currency": ""},
        "product": {"underlying": "000300.SH", "currency": ""},
        "product_kwargs": {},
    })
    assert product_payload["product"]["currency"] == "CNY"


def test_changed_record_cannot_be_confirmed_by_old_receipt(session):
    from app.services.domains.booking_verification import verify_booking
    _, _, config = setup_scope(session)
    portfolio = Portfolio(name="Book", base_currency="USD", kind=PortfolioKind.CONTAINER.value)
    session.add(portfolio); session.commit()
    position = book(session, portfolio, build_product("BarrierOption", RAW, underlying="MSFT").product_spec)
    capture(config, "book_position", {"portfolio_id": portfolio.id}, {"ok": True, "position": {"id": position.id}}, "book")
    position.quantity = 2
    session.commit()
    result = verify_booking(session, workflow_id=config["configurable"]["workflow_id"], portfolio_id=portfolio.id, position_id=position.id)
    assert result["terminal"] and result["verdict"] == "mismatch"
    assert "booking_record" in result["differences"]


def test_multiple_bookings_remain_inconclusive_without_position_id(session):
    from app.services.domains.booking_verification import verify_booking
    _, _, config = setup_scope(session)
    portfolio = Portfolio(name="Book", base_currency="USD", kind=PortfolioKind.CONTAINER.value)
    session.add(portfolio); session.commit()
    for i in range(2):
        position = book(session, portfolio, build_product("BarrierOption", RAW, underlying="MSFT").product_spec)
        capture(config, "book_position", {"portfolio_id": portfolio.id}, {"ok": True, "position": {"id": position.id}}, f"book{i}")
    result = verify_booking(session, workflow_id=config["configurable"]["workflow_id"], portfolio_id=portfolio.id, underlying="MSFT")
    assert not result["terminal"] and result["verdict"] == "ambiguous_booking"


@pytest.mark.asyncio
async def test_actual_persona_handoff_finishes_after_one_verification(session):
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langgraph.checkpoint.memory import InMemorySaver
    from app.services.deep_agent.orchestrator import build_orchestrator
    from app.services.agents import select_deep_agent_tools
    _, _, config = setup_scope(session)
    portfolio = Portfolio(name="Book", base_currency="USD", kind=PortfolioKind.CONTAINER.value)
    session.add(portfolio); session.commit()
    class Model(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self
    model = Model(responses=[
        AIMessage(content="", tool_calls=[{"name": "task", "id": "t", "args": {"subagent_type": "trader", "description": "Use position-snapshot. Confirm the position we just booked."}}]),
        AIMessage(content="", tool_calls=[{"name": "verify_position_booking", "id": "v", "args": {"portfolio_id": portfolio.id, "underlying": "MSFT"}}]),
        AIMessage(content="ERROR: a model call after terminal verification would reopen the audit"),
    ])
    graph = build_orchestrator(model=model, tools=select_deep_agent_tools(), checkpointer=InMemorySaver())
    config["recursion_limit"] = 30
    result = await graph.ainvoke({"messages": [HumanMessage(content="Confirm the position we just booked.")]}, config)
    assert "No booking receipt" in result["messages"][-1].content
    assert model.i == 2  # only orchestrator delegation and persona tool selection
    assert sum(c["name"] == "task" for m in result["messages"] if isinstance(m, AIMessage) for c in m.tool_calls) == 1


@pytest.mark.asyncio
async def test_actual_persona_validation_grounds_orchestrator_without_redelegation(session):
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langgraph.checkpoint.memory import InMemorySaver
    from app.services.deep_agent.orchestrator import build_orchestrator
    from app.services.agents import select_deep_agent_tools
    _, user, config = setup_scope(session)
    user.content = "Check BarrierOption native_product_terms completeness."
    session.commit()
    class Model(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self
    native = build_product("BarrierOption", RAW).product_kwargs
    model = Model(responses=[
        AIMessage(content="", tool_calls=[{"name": "task", "id": "t", "args": {"subagent_type": "trader", "description": "Check native BarrierOption terms."}}]),
        AIMessage(content="", tool_calls=[{"name": "check_term_completeness", "id": "v", "args": {"quantark_class": "BarrierOption", "terms": native, "representation": "native_product_terms"}}]),
        AIMessage(content="BarrierOption is ready to book under native_product_terms; no missing required terms."),
        AIMessage(content="BarrierOption is ready to book under native_product_terms; no missing required terms."),
        AIMessage(content="ERROR: redundant grounding nudge"),
    ])
    graph = build_orchestrator(model=model, tools=select_deep_agent_tools(), checkpointer=InMemorySaver())
    config["recursion_limit"] = 30
    result = await graph.ainvoke({"messages": [HumanMessage(content=user.content)]}, config)
    assert "ready to book" in result["messages"][-1].content
    assert model.i == 4
    assert not any("desk-guardrail:term-grounding" in str(m.content) for m in result["messages"])
