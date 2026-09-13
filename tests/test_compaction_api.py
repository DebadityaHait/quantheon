from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langgraph.checkpoint.memory import InMemorySaver

from test_api import make_client
from app.services.deep_agent.compaction import LedgerScopedCompactionMiddleware
from test_progressive_compaction import reply


def install_graph(client, monkeypatch, thread_id):
    from app.main import agent_service
    model = GenericFakeChatModel(messages=iter([AIMessage(content="ready"), reply("Reviewed the book; continue ticket")]))
    m = LedgerScopedCompactionMiddleware(model, backend=None, trigger=("tokens", 1000000), keep_recent=6)
    graph = create_agent(model=model, middleware=[m], checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(thread_id)}}
    asyncio.run(graph.ainvoke({"messages": [
        HumanMessage(content="review " + "x" * 4000), AIMessage(content="done " + "y" * 4000),
        HumanMessage(content="prepare ticket"), AIMessage(content="working"),
        HumanMessage(content="check details"), AIMessage(content="checked"),
        HumanMessage(content="finish"),
    ]}, config))
    @asynccontextmanager
    async def streaming_agent(*args, **kwargs):
        yield graph
    monkeypatch.setattr(agent_service, "_streaming_agent", streaming_agent)
    monkeypatch.setattr("app.services.agents.build_agent_model", lambda *args: model)
    return graph, config


def test_manual_endpoint_compacts_actual_checkpoint(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    thread = client.post("/api/chat/threads", json={"title": "test", "character": "trader"}).json()
    graph, config = install_graph(client, monkeypatch, thread["id"])
    response = client.post(f"/api/chat/threads/{thread['id']}/compact")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "compacted"
    state = asyncio.run(graph.aget_state(config))
    assert state.values["_summarization_event"]["cutoff_index"] == 2
    assert not state.next
    assert "finish" in state.values["_summarization_event"]["summary_message"].text


def test_manual_endpoint_refuses_pending_checkpoint(tmp_path, monkeypatch):
    from app.main import agent_service
    client = make_client(tmp_path)
    thread = client.post("/api/chat/threads", json={"title": "test", "character": "trader"}).json()
    graph, config = install_graph(client, monkeypatch, thread["id"])
    async def pending(*args):
        return SimpleNamespace(values={"messages": [HumanMessage(content="approve")]}, next=("tools",), tasks=())
    monkeypatch.setattr(agent_service, "_read_stream_state", pending)
    response = client.post(f"/api/chat/threads/{thread['id']}/compact")
    assert response.status_code == 409


def test_compact_slash_command_does_not_route_business_work(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    thread = client.post("/api/chat/threads", json={"title": "test", "character": "trader"}).json()
    install_graph(client, monkeypatch, thread["id"])
    response = client.post(f"/api/chat/threads/{thread['id']}/messages/stream", json={"content": "/compact"})
    assert response.status_code == 200
    assert "Conversation compacted" in response.text
    assert "event: done" in response.text


def test_manual_endpoint_refuses_concurrent_stream(tmp_path, monkeypatch):
    from app.services.deep_agent.run_control import checkpoint_operation
    client = make_client(tmp_path)
    thread = client.post("/api/chat/threads", json={"title": "test", "character": "trader"}).json()
    install_graph(client, monkeypatch, thread["id"])
    with checkpoint_operation(str(thread["id"])):
        response = client.post(f"/api/chat/threads/{thread['id']}/compact")
    assert response.status_code == 409
