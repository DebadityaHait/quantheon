from __future__ import annotations

import json

import pytest
from deepagents.backends import StateBackend
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services.deep_agent.compaction import LedgerScopedCompactionMiddleware


def reply(summary="Continue the user's review.", keys=()):
    return AIMessage(content=json.dumps({"summary": summary, "retained_reference_keys": list(keys)}))


def compactor(responses, **kwargs):
    return LedgerScopedCompactionMiddleware(
        GenericFakeChatModel(messages=iter(responses)), backend=StateBackend(), **kwargs
    )


def test_signature_does_not_erase_summary_input_or_mutate_wire_message():
    message = AIMessage(content=[
        {"type": "reasoning", "reasoning": "", "extras": {"signature": "x" * 100_000}},
        {"type": "text", "text": "Review finished; next prepare the ticket."},
    ])
    m = compactor([reply()], summary_input_tokens=4000)
    result = m._create_summary([HumanMessage(content="Review this trade"), message])
    assert "Continue" in result
    assert message.content[0]["extras"]["signature"] == "x" * 100_000
    from app.services.deep_agent.compaction import _count_tokens_approximately
    assert _count_tokens_approximately([message]) < 100


@pytest.mark.parametrize("output", [
    AIMessage(content=""),
    reply("Previous conversation was too long to summarize."),
    AIMessage(content=json.dumps({"summary": "fine", "retained_reference_keys": []}),
              response_metadata={"stop_reason": "max_tokens"}),
    reply(keys=["artifact:999"]),
])
def test_invalid_summary_is_refused(output):
    from app.services.deep_agent.compaction import CompactionError
    with pytest.raises(CompactionError):
        compactor([output])._create_summary([HumanMessage(content="Review the book")])


def test_no_progress_summary_prefix_is_not_compacted():
    m = compactor([])
    summary = HumanMessage(content="previous summary", additional_kwargs={"lc_source": "summarization"})
    messages = [summary, AIMessage(content="", tool_calls=[
        {"id": "a", "name": "read_artifact", "args": {}, "type": "tool_call"}
    ]), ToolMessage(content="failed", status="error", name="read_artifact", tool_call_id="a")]
    # Verified error pairs are safe to summarize; an uncaptured success is not.
    messages[2] = messages[2].model_copy(update={"status": "success"})
    m.ground_truth_tool_names = frozenset({"read_artifact"})
    assert m._determine_cutoff_index(messages + [AIMessage(content="tail")] * 6) == 0


def test_protected_tool_error_can_compact_but_success_cannot():
    from app.services.deep_agent.compaction import is_compactable_message
    error = ToolMessage(content="missing section", status="error", name="read_artifact", tool_call_id="a")
    assert is_compactable_message(error, ground_truth_tool_names={"read_artifact"})
    assert not is_compactable_message(error.model_copy(update={"status": "success"}),
                                      ground_truth_tool_names={"read_artifact"})


def test_repeated_compaction_preserves_only_selected_server_references():
    ref = {"artifact_id": 17, "kind": "tool_result", "content_hash": "sha256:" + "a" * 64,
           "tool_call_id": "call", "tool_name": "get_rfq", "generated_at": "2026-10-12T00:00:00Z",
           "locator": "/large_tool_results/call", "summary": {"ids": {"rfq_id": 5}}}
    raw = ToolMessage(content='{"premium": 123456789}', name="get_rfq", tool_call_id="call",
                      additional_kwargs={"artifact_ref": ref, "artifact_ref_provenance": "server_capture_v1"})
    m = compactor([reply(keys=["artifact:17"]), reply(keys=["artifact:17"])])
    first = m._create_summary([HumanMessage(content="Review"), raw])
    summary = m._build_new_messages_with_path(first, "/conversation_history/history.md")[0]
    second = m._create_summary([summary, AIMessage(content="Continue review")])
    assert '"artifact_id":17' in second.replace(" ", "")
    assert "123456789" not in second
    assert "inspect_artifact" in second and "read_artifact" in second


def test_config_threshold_is_validated(monkeypatch):
    from app.config import Settings
    monkeypatch.setenv("OPEN_OTC_COMPACTION_THRESHOLD_FRACTION", "0.6")
    monkeypatch.setenv("OPEN_OTC_COMPACTION_THRESHOLD_TOKENS", "80000")
    assert Settings().agent_compaction_threshold_fraction == 0.6
    assert Settings().agent_compaction_threshold_tokens == 80000
    monkeypatch.setenv("OPEN_OTC_COMPACTION_THRESHOLD_FRACTION", "1.2")
    with pytest.raises(ValueError):
        Settings()


@pytest.mark.asyncio
async def test_manual_compaction_preserves_current_work_and_recoverable_history():
    m = compactor([reply("Completed review. Prepare the ticket.")], keep_recent=2)
    state = {"messages": [HumanMessage(content="Review trade " + "x" * 4000),
                          AIMessage(content="Reviewed " + "y" * 4000),
                          HumanMessage(content="Prepare the ticket now"), AIMessage(content="Working")],
             "todos": [{"content": "Prepare ticket", "status": "in_progress"}]}
    update = await m.compact_state(state)
    assert update["_summarization_event"]["cutoff_index"] == 2
    assert "Prepare the ticket now" in update["_summarization_event"]["summary_message"].text
    assert "in_progress" in update["_summarization_event"]["summary_message"].text
    assert "Review trade" in next(iter(update["files"].values()))["content"]
    assert "_summarization_event" not in state


@pytest.mark.asyncio
async def test_automatic_bad_summary_preserves_context_and_records_failure(monkeypatch):
    from langchain.agents.middleware.types import ModelRequest, ModelResponse
    m = compactor([AIMessage(content="")], trigger=("tokens", 1), keep_recent=2)
    monkeypatch.setattr(m, "_aoffload_to_backend", _offload_stub)
    messages = [HumanMessage(content="Review " + "x" * 4000),
                AIMessage(content="done " + "y" * 4000), HumanMessage(content="continue"), AIMessage(content="ok")]
    state = {"messages": messages}
    seen = []
    async def handler(request):
        seen.append(request.messages)
        return ModelResponse(result=[AIMessage(content="continued")])
    request = ModelRequest(model=m.model, messages=messages, state=state)
    result = await m.awrap_model_call(request, handler)
    assert seen == [messages]
    assert "_summarization_event" not in result.command.update
    assert "_compaction_failure" in result.command.update


@pytest.mark.asyncio
async def test_automatic_and_manual_use_the_same_reference_contract(monkeypatch):
    from langchain.agents.middleware.types import ModelRequest, ModelResponse
    m = compactor([reply("Completed review; continue ticket")], trigger=("tokens", 1), keep_recent=2)
    monkeypatch.setattr(m, "_aoffload_to_backend", _offload_stub)
    messages = [HumanMessage(content="Review " + "x" * 4000),
                AIMessage(content="done " + "y" * 4000), HumanMessage(content="continue"), AIMessage(content="ok")]
    async def handler(request):
        assert "<current_work>" in request.messages[0].text
        return ModelResponse(result=[AIMessage(content="continued")])
    request = ModelRequest(model=m.model, messages=messages, state={"messages": messages, "todos": []})
    result = await m.awrap_model_call(request, handler)
    assert result.command.update["_summarization_event"]["cutoff_index"] == 2


@pytest.mark.asyncio
async def test_manual_compaction_checkpoint_is_idle_after_update():
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver
    m = compactor([AIMessage(content="done"), reply("Reviewed; next ticket")], trigger=("tokens", 1000000), keep_recent=2)
    graph = create_agent(model=m.model, tools=[], middleware=[m], checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "manual"}}
    await graph.ainvoke({"messages": [HumanMessage(content="old " + "x" * 4000),
                                      AIMessage(content="old " + "y" * 4000),
                                      HumanMessage(content="prepare ticket")]}, config)
    state = await graph.aget_state(config)
    assert not state.next
    update = await m.compact_state(state.values)
    await graph.aupdate_state(state.config, update, as_node="model")
    compacted = await graph.aget_state(config)
    assert not compacted.next
    assert compacted.values["_summarization_event"]["cutoff_index"] == 2


async def _offload_stub(*args):
    return "/conversation_history/test.md"


def test_saved_records_are_scoped_and_progressively_read(session):
    from app.models import AgentThread, Workflow, AgentTask, RFQ, SessionArtifact
    from app.services.deep_agent.artifact_access import read_saved_record
    thread = AgentThread(title="test", character="auto")
    session.add(thread); session.flush()
    a = Workflow(thread_id=thread.id, title="a", intent="desk")
    b = Workflow(thread_id=thread.id, title="b", intent="desk")
    session.add_all([a, b]); session.flush()
    task = AgentTask(workflow_id=a.id, task_type="review", assigned_persona="trader", inputs={"long": "body"})
    rfq = RFQ(client_name="client", request_payload={"product": {"strike": 123.45}})
    session.add_all([task, rfq]); session.flush()
    receipt = SessionArtifact(workflow_id=a.id, kind="tool_result", title="saved RFQ",
                              payload={"summary_provenance": "deterministic", "summary": {"ids": {"rfq_id": rfq.id}}})
    session.add(receipt); session.commit()
    card = read_saved_record(session, workflow_id=a.id, kind="rfq", record_id=rfq.id)
    assert "content" not in card
    body = read_saved_record(session, workflow_id=a.id, kind="rfq", record_id=rfq.id,
                             json_pointer="/request_payload/product")
    assert "123.45" in body["content"]
    for kind, record_id in [("task", task.id), ("rfq", rfq.id)]:
        with pytest.raises(ValueError):
            read_saved_record(session, workflow_id=b.id, kind=kind, record_id=record_id)


def test_long_report_is_saved_and_selectable_without_body_in_summary(session):
    from app.models import AgentThread, AgentTask, SessionArtifact
    from app.services.deep_agent.workflow_state import ensure_thread_workflow_state
    from app.services.deep_agent.compaction import _REQUEST_CONFIG, _scoped_catalog
    thread = AgentThread(title="reports", character="trader")
    session.add(thread); session.flush()
    state = ensure_thread_workflow_state(session, thread.id)
    task = AgentTask(workflow_id=state.meta_workflow_id, task_type="review_report",
                     assigned_persona="orchestrator", status="running", inputs={"huge": "z" * 10000})
    session.add(task); session.commit()
    config = {"configurable": {"workflow_id": state.meta_workflow_id,
                                "session_id": state.orchestrator_session_id}}
    token = _REQUEST_CONFIG.set(config)
    try:
        m = compactor([])
        report = AIMessage(content="Report body " + "secret-number-123456 " * 400)
        captured = m._capture_long_messages([report])
        ref = captured[0].additional_kwargs["artifact_ref"]
        prompt, catalog = m._summary_input([HumanMessage(content="continue report"), *captured])
        assert "secret-number-123456" not in prompt
        assert f"artifact:{ref['artifact_id']}" in catalog
        assert _scoped_catalog()[f"task:{task.id}"]["required"]
        assert "z" * 100 not in prompt
        selected = m._validated_summary(reply(keys=[f"artifact:{ref['artifact_id']}"]), catalog)
        assert f'"task_id":{task.id}' in selected
        stored = session.get(SessionArtifact, ref["artifact_id"])
        from app.services.deep_agent.artifact_access import raw_artifact_content
        assert raw_artifact_content(stored) == report.text
    finally:
        _REQUEST_CONFIG.reset(token)


def test_summary_model_effort_is_independent_of_execution_model():
    from app.config import Settings
    from app.services.deep_agent.compaction import _summary_runner
    from langchain_openai import ChatOpenAI
    model = ChatOpenAI(model="test", api_key="dummy", extra_body={"reasoning_effort": "max"})
    runner = _summary_runner(model, Settings())
    assert model.extra_body["reasoning_effort"] == "max"
    assert runner.bound.extra_body["reasoning_effort"] == "low"
    assert runner.bound.max_tokens == 4096


def test_visible_manifest_is_compact_and_full_provenance_stays_in_metadata():
    from app.services.deep_agent.compaction import _artifact_card
    reference = {"artifact_id": 44, "kind": "tool_result", "content_hash": "sha256:" + "a" * 64,
                 "tool_call_id": "private-tool-call", "tool_name": "get_positions",
                 "generated_at": "2026-10-12T00:00:00Z", "locator": "/large_tool_results/a",
                 "summary": {"top_level_keys": ["very-long-internal-field-" + "x" * 2000]}}
    catalog = {"artifact:44": _artifact_card(reference)}
    result = compactor([])._validated_summary(reply(keys=["artifact:44"]), catalog)
    assert "<artifact_manifest>" not in result
    assert result.count('"artifact_id"') == 1
    assert "private-tool-call" not in result and "very-long-internal-field" not in result
    assert result.references[0]["reference"] == reference


def test_retained_and_reference_budgets_are_independent_of_generation_limit():
    from dataclasses import replace
    from app.config import Settings
    settings = replace(Settings(), agent_compaction_summary_output_tokens=512,
                       agent_compaction_retained_tokens=4096, agent_compaction_reference_tokens=2048)
    m = compactor([], settings=settings)
    result = m._validated_summary(reply("word " * 600), {})
    assert len(result) // 4 > 512  # server-rendered context uses its own limit


@pytest.mark.asyncio
async def test_rejected_prefix_is_not_retried_when_only_tail_grows(monkeypatch):
    from langchain.agents.middleware.types import ModelRequest, ModelResponse
    from app.services.deep_agent.compaction import CompactionError
    m = compactor([], trigger=("tokens", 1), keep_recent=2, max_messages=2)
    monkeypatch.setattr(m, "_aoffload_to_backend", _offload_stub)
    attempts = []
    async def reject(messages):
        attempts.append(messages)
        # Exercise the real attempt identity without making a model call.
        m._remember_attempt(messages)
        raise CompactionError("oversized references")
    monkeypatch.setattr(m, "_acreate_summary", reject)
    messages = [HumanMessage(content="Review " + "x" * 4000), AIMessage(content="done " + "y" * 4000),
                HumanMessage(content="continue"), AIMessage(content="ok")]
    async def handler(request):
        return ModelResponse(result=[AIMessage(content="continued")])
    first = await m.awrap_model_call(ModelRequest(model=m.model, messages=messages, state={"messages": messages}), handler)
    failure = first.command.update["_compaction_failure"]
    more = [*messages, AIMessage(content="another tool result arrived")]
    second = await m.awrap_model_call(ModelRequest(model=m.model, messages=more,
                                     state={"messages": more, "_compaction_failure": failure}), handler)
    assert len(attempts) == 1
    assert second.result[0].text == "continued"
    new_work = [*more, HumanMessage(content="Now review another trade")]
    await m.awrap_model_call(ModelRequest(model=m.model, messages=new_work,
                            state={"messages": new_work, "_compaction_failure": failure}), handler)
    assert len(attempts) == 2  # new user intent allows another bounded attempt


def test_reference_budget_refuses_without_silently_dropping_selected_keys():
    from app.services.deep_agent.compaction import _artifact_card, CompactionError
    from app.config import Settings
    from dataclasses import replace
    ref = {"artifact_id": 1, "kind": "tool_result", "tool_name": "get_rfq",
           "content_hash": "sha256:" + "a" * 64, "tool_call_id": "x",
           "generated_at": "2026-10-12T00:00:00Z", "locator": "/large_tool_results/x"}
    catalog = {f"artifact:{i}": _artifact_card(dict(ref, artifact_id=i)) for i in range(1, 5)}
    settings = replace(Settings(), agent_compaction_reference_tokens=128)
    with pytest.raises(CompactionError, match="reference budget"):
        compactor([], settings=settings)._validated_summary(reply(keys=list(catalog)), catalog)


def test_full_wrapper_is_included_in_retained_context_limit():
    from app.services.deep_agent.compaction import CompactionError, _REQUEST_STATE
    from app.config import Settings
    from dataclasses import replace
    settings = replace(Settings(), agent_compaction_retained_tokens=512, agent_compaction_reference_tokens=128)
    m = compactor([], settings=settings)
    result = m._validated_summary(reply(), {})
    token = _REQUEST_STATE.set({"messages": [HumanMessage(content="current instruction " * 1000)]})
    try:
        with pytest.raises(CompactionError, match="current work"):
            m._build_new_messages_with_path(result, "/conversation_history/history.md")
    finally:
        _REQUEST_STATE.reset(token)
