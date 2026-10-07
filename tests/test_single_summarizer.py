"""Every agent stack carries exactly ONE summarization middleware.

deepagents 0.7 adds its own `SummarizationMiddleware` to every stack it builds and
lets a caller's middleware REPLACE it only when the `.name` matches; a subclass's
name falls back to its class name. `LedgerScopedCompactionMiddleware` was therefore
APPENDED, and the orchestrator ran two summarizers sharing one
`_summarization_event`. After the first compaction (cutoff c) the outer one passed
`[summary] + state[c:]` down and ours applied the event AGAIN, so the model saw
`[summary] + state[2c-1:]`: c-1 messages silently lost, and a 400 on every later
call whenever that slice opened on a ToolMessage (run #145, five deepseek threads).

The assertion is structural on purpose: it builds the real orchestrator through
the real `create_deep_agent`, so a future rename upstream cannot bring the
duplicate back silently.
"""
from __future__ import annotations

import dataclasses

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel


def _captured_stacks(monkeypatch) -> list[tuple[str, list]]:
    import deepagents.graph as graph
    import deepagents.middleware.subagents as subagents

    stacks: list[tuple[str, list]] = []
    for module in (graph, subagents):
        real = module.create_agent

        def spy(*args, _real=real, **kwargs):
            stacks.append((str(kwargs.get("name")), list(kwargs.get("middleware") or [])))
            return _real(*args, **kwargs)

        monkeypatch.setattr(module, "create_agent", spy)

    from app.config import Settings
    from app.services.deep_agent.checkpointer import build_checkpointer
    from app.services.deep_agent.orchestrator import build_orchestrator

    settings = dataclasses.replace(Settings(), agent_checkpoint_db_path=":memory:")
    build_orchestrator(
        model=GenericFakeChatModel(messages=iter([])),
        tools=[],
        checkpointer=build_checkpointer(settings),
        yolo_mode=True,
        allow_reply_options=False,
    )
    return stacks


def test_every_stack_has_exactly_one_summarizer(monkeypatch):
    from deepagents.middleware.summarization import SummarizationMiddleware

    stacks = _captured_stacks(monkeypatch)
    assert any(name == "otc_desk_orchestrator" for name, _ in stacks)
    for name, middleware in stacks:
        summarizers = [type(m).__name__ for m in middleware
                       if isinstance(m, SummarizationMiddleware)]
        assert len(summarizers) == 1, (name, summarizers)
        assert summarizers == ["LedgerScopedCompactionMiddleware"], name


def test_the_orchestrator_summarizer_is_the_ledger_scoped_one(monkeypatch):
    from deepagents.middleware.summarization import SummarizationMiddleware

    from app.services.deep_agent.compaction import LedgerScopedCompactionMiddleware

    stacks = dict(_captured_stacks(monkeypatch))
    orchestrator = stacks["otc_desk_orchestrator"]
    (summarizer,) = [m for m in orchestrator if isinstance(m, SummarizationMiddleware)]
    assert isinstance(summarizer, LedgerScopedCompactionMiddleware)
    # It must sit OUTSIDE every other message-rewriting middleware we add: its
    # `cutoff_index` is a STATE index, so request.messages must still be state.
    ours = {"ToolErrorBoundaryMiddleware", "GroundTruthArtifactMiddleware",
            "DeskContextMiddleware", "TermGroundingMiddleware"}
    position = orchestrator.index(summarizer)
    assert all(orchestrator.index(m) > position
               for m in orchestrator if type(m).__name__ in ours)
