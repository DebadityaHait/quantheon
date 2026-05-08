"""Ledger-aware compaction controls for task-scoped DeepAgents sessions."""
from __future__ import annotations

import json
import re
import hashlib
import copy
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage, get_buffer_string
from langchain.agents.middleware.types import ExtendedModelResponse, PrivateStateAttr
from langgraph.types import Command
from deepagents.middleware.summarization import SummarizationState, DEEPAGENTS_DEFAULT_SUMMARY_PROMPT
from typing_extensions import NotRequired, Annotated

from .cas_backend import ARTIFACT_REFERENCE_PROVENANCE


def _summarization_middleware_base() -> type:
    from deepagents.middleware.summarization import SummarizationMiddleware

    return SummarizationMiddleware


PROTECTED_ARTIFACT_KINDS = {
    "persisted_run",
    "deterministic_query",
    "finding",
    "report",
    "plan",
}

PERSISTED_TOOL_NAMES = {
    "task",
    "run_batch_pricing",
    "create_report",
    "import_otc_positions",
    "create_or_update_rfq_draft",
    "quote_rfq",
    "submit_rfq_for_approval",
    "approve_rfq",
    "reject_rfq",
    "release_rfq",
    "mark_rfq_client_accepted",
    "book_rfq_to_position",
}

LEDGER_AWARE_SUMMARY_PROMPT = """<role>
Ledger-aware context compactor for an OTC derivatives desk agent session.
</role>

<instructions>
Summarize only compactable ephemeral conversation history. Never treat this summary
as financial truth; durable facts live in DB tables, session_artifacts, evidence refs,
domain_events, /large_tool_results/, /trading_desk/, /artifacts/, and /session/findings/.

Every substantive factual sentence in the summary must end with an existing
ledger/tool citation: [artifact:N] or [tool_call:id]. If a factual statement has no
such citation, omit it or rewrite it as an unresolved note.

Do not restate prices, Greeks, positions, run results, report figures, database rows,
or other ground-truth payloads. Refer only to their supplied artifact capsule. The
runtime appends the authoritative artifact manifest after your narrative summary;
you must not recreate, edit, or extend that manifest.

Preserve pending HITL state, user intent, blocker state, and next action. Do not
invent artifact ids, tool_call ids, prices, risk metrics, trade ids, dates, or
approval status.

Remove redundant tool traces and obsolete reasoning; preserve decisions, todos,
task progress, user constraints, unresolved work and next steps. Long reports and
structured RFQ/task contents are progressively disclosed: retain their reference
keys and short descriptions, never their full contents. Select the keys needed
in the next window from the supplied server catalog, including dependencies.
The runtime supplies exact ids, locators and retrieval methods for your selection.
Return ONLY JSON with two fields: "summary" (a concise narrative string) and
"retained_reference_keys" (an array of existing catalog keys). Do not invent keys.
</instructions>

<messages>
Messages to summarize:
{messages}
</messages>
"""

DEFAULT_TOKEN_TRIGGER_FALLBACK = ("tokens", 100_000)


class CompactionError(ValueError):
    """A compaction cannot safely replace working context."""


class ProgressiveCompactionState(SummarizationState):
    _compaction_failure: NotRequired[Annotated[dict[str, Any] | None, PrivateStateAttr]]


_REQUEST_STATE: ContextVar[dict[str, Any]] = ContextVar("compaction_request_state", default={})
_REQUEST_CONFIG: ContextVar[dict[str, Any] | None] = ContextVar("compaction_request_config", default=None)
_ATTEMPT: ContextVar[dict[str, Any] | None] = ContextVar("compaction_attempt", default=None)

SUMMARY_CALL_CONFIG = {"metadata": {"lc_source": "summarization", "open_otc_internal": "compaction"},
                       "tags": ["open-otc-compaction", "nostream"]}

DISCLOSURE_METHODS = (
    "Artifact cards: inspect_artifact(artifact_id), then read_artifact with the returned section/json_pointer "
    "and bounded offset/limit. Full provenance remains in the scoped artifact store; verify it before acting. "
    "Task/RFQ cards: read_saved_record(kind, record_id) for its section map, then a bounded json_pointer read. "
    "Use the exact kind: task is AgentTask; task_run is a background TaskRun. "
    "Validate raw_build_inputs, native_product_terms and valuation_market separately. "
    "Fixing references/provenance belong outside constructor kwargs."
)


class _Summary(str):
    references: list[dict[str, Any]]

    def __new__(cls, text: str, references: list[dict[str, Any]]):
        result = super().__new__(cls, text)
        result.references = references
        return result


@dataclass(frozen=True)
class CompactionBatch:
    start: int
    end: int


def select_compaction_batch(
    messages: list[BaseMessage],
    *,
    keep_recent: int = 6,
    max_messages: int = 8,
    ground_truth_tool_names: set[str] | frozenset[str] = frozenset(),
) -> CompactionBatch | None:
    """Return the first consecutive compactable batch outside the recent tail."""
    limit = max(0, len(messages) - keep_recent)
    start: int | None = None
    end: int | None = None
    for index, message in enumerate(messages[:limit]):
        if is_compactable_message(
            message,
            ground_truth_tool_names=ground_truth_tool_names,
        ):
            if start is None:
                start = index
            end = index + 1
            if end - start >= max_messages:
                break
            continue
        if start is not None:
            break

    if start is None or end is None:
        return None
    return CompactionBatch(start=start, end=end)


def is_compactable_message(
    message: BaseMessage,
    *,
    ground_truth_tool_names: set[str] | frozenset[str] = frozenset(),
) -> bool:
    if isinstance(message, ToolMessage):
        tool_name = _message_tool_name(message)
        if message.status == "error":
            return True  # no financial success payload; retain the call/error together
        if _message_artifact_ref(message) is not None:
            return True
        return tool_name not in (set(ground_truth_tool_names) | PERSISTED_TOOL_NAMES)
    if isinstance(message, AIMessage):
        if _message_artifact_ref(message) is not None:
            return True
        return _message_artifact_kind(message) not in PROTECTED_ARTIFACT_KINDS
    return True


_ARTIFACT_REF_REQUIRED = frozenset(
    {
        "artifact_id",
        "kind",
        "content_hash",
        "tool_call_id",
        "generated_at",
        "locator",
    }
)


def _valid_artifact_ref(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not _ARTIFACT_REF_REQUIRED <= value.keys():
        return None
    if not isinstance(value.get("artifact_id"), int):
        return None
    if not str(value.get("content_hash") or "").startswith("sha256:"):
        return None
    if not str(value.get("generated_at") or ""):
        return None
    if not str(value.get("locator") or ""):
        return None
    return dict(value)


def _message_artifact_ref(message: BaseMessage) -> dict[str, Any] | None:
    metadata = getattr(message, "additional_kwargs", {}) or {}
    if metadata.get("artifact_ref_provenance") != ARTIFACT_REFERENCE_PROVENANCE:
        return None
    return _valid_artifact_ref(metadata.get("artifact_ref"))


def project_compaction_messages(
    messages: list[BaseMessage],
) -> tuple[list[BaseMessage], list[dict[str, Any]]]:
    """Replace raw evidence bodies with exact server-generated reference capsules."""
    projected: list[BaseMessage] = []
    by_id: dict[int, dict[str, Any]] = {}
    call_refs = {m.tool_call_id: _message_artifact_ref(m) for m in messages
                 if isinstance(m, ToolMessage) and _message_artifact_ref(m) is not None}
    for message in messages:
        reference = _message_artifact_ref(message)
        if reference is None:
            if isinstance(message, AIMessage) and message.tool_calls:
                # Exact arguments remain in the archived history. The summarizer
                # needs the action/result linkage, not another full RFQ/report.
                calls = [dict(call, args={"saved_result_artifact_id": call_refs[call["id"]]["artifact_id"],
                                          "exact_arguments": "archived conversation history"})
                         if call["id"] in call_refs else call for call in message.tool_calls]
                content = message.content
                if isinstance(content, list):
                    content = [b for b in content if not isinstance(b, dict) or b.get("type") != "tool_use"]
                projected.append(message.model_copy(update={"tool_calls": calls, "content": content}))
            else:
                projected.append(message)
            continue
        by_id.setdefault(int(reference["artifact_id"]), reference)
        capsule = json.dumps(
            reference,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        projected.append(
            message.model_copy(update={"content": f"<artifact_ref>{capsule}</artifact_ref>"})
        )
    return projected, [by_id[key] for key in sorted(by_id)]


def append_artifact_manifest(
    summary: str,
    references: list[dict[str, Any]],
) -> str:
    if not references:
        return summary
    # Artifact tags are a server-owned channel. Remove any model-authored copy
    # before appending the one canonical manifest so a prompt/model cannot spoof
    # an executable reference inside narrative text.
    narrative = re.sub(
        r"<artifact_(?:manifest|ref)\b[^>]*>.*?</artifact_(?:manifest|ref)>",
        "",
        summary,
        flags=re.IGNORECASE | re.DOTALL,
    )
    narrative = re.sub(
        r"</?artifact_(?:manifest|ref)\b[^>]*>",
        "",
        narrative,
        flags=re.IGNORECASE,
    ).strip()
    manifest = json.dumps(
        references,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        default=str,
    )
    return (
        f"{narrative}\n\n"
        "<artifact_manifest>\n"
        f"{manifest}\n"
        "</artifact_manifest>"
    )


def _message_tool_name(message: BaseMessage) -> str | None:
    name = getattr(message, "name", None)
    if name:
        return str(name)
    metadata = getattr(message, "additional_kwargs", {}) or {}
    for key in ("tool_name", "name"):
        value = metadata.get(key)
        if value:
            return str(value)
    return None


def _message_artifact_kind(message: BaseMessage) -> str | None:
    for payload in (
        getattr(message, "additional_kwargs", {}) or {},
        getattr(message, "response_metadata", {}) or {},
    ):
        kind = _artifact_kind_from_mapping(payload)
        if kind:
            return kind
    return None


def _artifact_kind_from_mapping(payload: dict[str, Any]) -> str | None:
    for key in ("artifact_kind", "kind"):
        value = payload.get(key)
        if value:
            return str(value)
    artifact = payload.get("artifact")
    if isinstance(artifact, dict):
        value = artifact.get("kind")
        if value:
            return str(value)
    return None


def _pair_safe_cutoff(messages: list[BaseMessage], cutoff: int) -> int:
    """Pull ``cutoff`` back so the kept tail never opens on a ``ToolMessage``.

    The batch ends wherever the size cap or a protected message stops it, which
    can be just after an ``AIMessage`` whose tool results fall on the kept side.
    Summarizing that call leaves them orphaned: most routes shrug, but DeepSeek's
    upstream rejects the request with a 400 on every later call, since the
    summary persists (run #143). Only ever moves BACK, into the summarized span:
    moving forward would summarize the protected result that stopped the batch.
    """
    while 0 < cutoff < len(messages) and isinstance(messages[cutoff], ToolMessage):
        cutoff -= 1
    return cutoff


class LedgerScopedCompactionMiddleware(_summarization_middleware_base()):
    """DeepAgents summarization constrained to compactable ledger-safe batches."""

    @property
    def name(self) -> str:
        """Claim deepagents' public alias so this REPLACES its default summarizer.

        deepagents 0.7 adds a `SummarizationMiddleware` to every stack and swaps
        in a caller's middleware only when the `.name` matches; a subclass's name
        falls back to its class name. Under that name this middleware was
        APPENDED, so the orchestrator ran two summarizers sharing one
        `_summarization_event`: after a compaction at cutoff c the outer one
        passed `[summary] + state[c:]` down and this one applied the event AGAIN,
        sending `[summary] + state[2c-1:]`. That silently dropped c-1 messages,
        and 400'd every later call on DeepSeek whenever the slice opened on a
        ToolMessage (run #145). Replacing in place also keeps this middleware
        outside every message-rewriting middleware we add, which its STATE-index
        cutoff requires. Guarded by tests/test_single_summarizer.py.
        """
        return "SummarizationMiddleware"

    state_schema = ProgressiveCompactionState

    def __init__(
        self,
        model: Any,
        *,
        backend: Any,
        trigger: Any = None,
        keep_recent: int | None = None,
        max_messages: int | None = None,
        summary_input_tokens: int | None = None,
        settings: Any = None,
        ground_truth_tool_names: set[str] | frozenset[str] = frozenset(),
    ) -> None:
        from app.config import get_settings
        settings = settings or get_settings()
        trigger = trigger or ("fraction", settings.agent_compaction_threshold_fraction)
        keep_recent = keep_recent if keep_recent is not None else settings.agent_compaction_keep_messages
        self.summary_input_tokens = summary_input_tokens or settings.agent_compaction_summary_input_tokens
        self.summary_output_tokens = settings.agent_compaction_summary_output_tokens
        self.retained_tokens = settings.agent_compaction_retained_tokens
        self.reference_tokens = settings.agent_compaction_reference_tokens
        self.keep_recent = keep_recent
        self.max_messages = max_messages
        self.requested_trigger = trigger
        self.ground_truth_tool_names = frozenset(ground_truth_tool_names)
        effective_trigger = (
            ("tokens", settings.agent_compaction_threshold_tokens)
            if _requires_model_profile(trigger) and not _has_model_profile(model)
            else trigger
        )
        super().__init__(
            model=model,
            backend=backend,
            trigger=effective_trigger,
            keep=("messages", keep_recent),
            token_counter=_count_tokens_approximately,
            summary_prompt=LEDGER_AWARE_SUMMARY_PROMPT,
            trim_tokens_to_summarize=None,
        )
        # Bind only summary-call settings. Never mutate the contestant model or
        # strip signatures from messages replayed on its wire.
        self._summary_runner = _summary_runner(model, settings)

    def _determine_cutoff_index(self, messages: list[BaseMessage]) -> int:
        deepagents_cutoff = super()._determine_cutoff_index(messages)
        if deepagents_cutoff <= 0:
            return 0

        batch = select_compaction_batch(
            list(messages[:deepagents_cutoff]),
            keep_recent=0,
            max_messages=self.max_messages or len(messages),
            ground_truth_tool_names=self.ground_truth_tool_names,
        )
        if batch is None or batch.start != 0:
            return 0
        cutoff = _pair_safe_cutoff(messages, batch.end)
        # A prior summary represents no new state messages. A summary-only batch
        # would keep the absolute cutoff unchanged and repeatedly spend tokens.
        if cutoff <= 1 and messages and self._is_summary_message(messages[0]):
            return 0
        # Select whole exchanges that fit. Nothing evicted is silently trimmed
        # away by the inherited `start_on=human, strategy=last` helper.
        while cutoff > 0:
            try:
                self._summary_input(messages[:cutoff])
                break
            except CompactionError:
                pass
            cutoff = _pair_safe_cutoff(messages, cutoff - 1)
        if cutoff <= 1 and messages and self._is_summary_message(messages[0]):
            return 0
        return cutoff

    def _create_summary(self, messages_to_summarize: list[BaseMessage]) -> str:
        self._remember_attempt(messages_to_summarize)
        prompt, catalog = self._summary_input(messages_to_summarize)
        response = self._summary_runner.invoke(prompt, config=SUMMARY_CALL_CONFIG)
        return self._validated_summary(response, catalog)

    def _offload_to_backend(self, backend, messages, session_id):
        path = super()._offload_to_backend(backend, messages, session_id)
        if path is None:
            raise CompactionError("Cannot save history before compaction")
        return path

    async def _aoffload_to_backend(self, backend, messages, session_id):
        path = await super()._aoffload_to_backend(backend, messages, session_id)
        if path is None:
            raise CompactionError("Cannot save history before compaction")
        return path

    async def _acreate_summary(
        self, messages_to_summarize: list[BaseMessage]
    ) -> str:
        self._remember_attempt(messages_to_summarize)
        prompt, catalog = self._summary_input(messages_to_summarize)
        response = await self._summary_runner.ainvoke(prompt, config=SUMMARY_CALL_CONFIG)
        return self._validated_summary(response, catalog)

    def _summary_input(self, messages: list[BaseMessage]) -> tuple[str, dict[str, dict[str, Any]]]:
        if not messages:
            raise CompactionError("No new history to compact")
        projected, refs = project_compaction_messages(messages)
        catalog = {f"artifact:{r['artifact_id']}": _artifact_card(r) for r in refs}
        for message in messages:
            if self._is_summary_message(message):
                for card in message.additional_kwargs.get("disclosure_references", []):
                    catalog[card["key"]] = card
        catalog.update(_scoped_catalog())
        # Selected prior build/RFQ cards also carry dated-fixing dependencies;
        # rehydrate those descriptors even after the build leaves recent history.
        fixing_ids = {ref["artifact_id"] for card in catalog.values()
                      for ref in card.get("reference", {}).get("summary", {}).get("fixing_references", [])}
        if fixing_ids:
            from app import database
            from app.models import SessionArtifact
            from .artifact_access import workflow_id_from_config, artifact_descriptor
            workflow = workflow_id_from_config(_REQUEST_CONFIG.get())
            with database.SessionLocal() as session:
                for aid in fixing_ids:
                    artifact = session.get(SessionArtifact, aid)
                    if artifact is None or artifact.workflow_id != workflow:
                        raise CompactionError("Fixing dependency is unavailable in current workflow")
                    card = _artifact_card(artifact_descriptor(artifact))
                    card["required"] = any(c.get("required") for c in catalog.values()
                        if aid in [r["artifact_id"] for r in c.get("reference", {}).get("summary", {}).get("fixing_references", [])])
                    catalog[card["key"]] = card
        # The prior manifest is server metadata, not material for the model to
        # paraphrase. Catalog entries remain selectable on every compaction.
        projected = [m.model_copy(update={"content": _strip_manifest(m.text)})
                     if self._is_summary_message(m) else m for m in projected]
        history = get_buffer_string(projected, format="xml")
        prompt = LEDGER_AWARE_SUMMARY_PROMPT.format(messages=history)
        # Keep the upstream strategy's preservation instructions, including
        # task/todo progress and media references, while our JSON contract owns
        # the output shape and exact data is represented by reference cards.
        guidance = DEEPAGENTS_DEFAULT_SUMMARY_PROMPT.split("<instructions>", 1)[1].split("</instructions>", 1)[0]
        prompt += "\n<upstream_summary_guidance>\n" + guidance + "\n</upstream_summary_guidance>"
        prompt += "\nUse these sections inside the summary string; the required JSON output contract takes precedence."
        # Put required work first, then other candidates. Full inventories stay
        # available via scoped discovery rather than bloating every summary.
        catalog = dict(sorted(catalog.items(), key=lambda item: not item[1].get("required", False)))
        cards = [_visible_card(card) for card in catalog.values()]
        for card, source in zip(cards, catalog.values()):
            card["required"] = bool(source.get("required"))
            card["retained_tokens"] = _text_tokens(json.dumps(_visible_card(source), ensure_ascii=False))
        prompt += "\n<reference_catalog>\n" + json.dumps(cards, ensure_ascii=False) + "\n</reference_catalog>"
        prompt += (f"\nReference selection budget: {self.reference_tokens} tokens including JSON framing and shared retrieval instructions. "
                   "Retain every required key, then select only the most useful optional keys within that budget. "
                   f"Total retained context budget: {self.retained_tokens} tokens including summary, references, current instruction and todos. "
                   "Keep the narrative concise; do not restate the cards or their metadata.")
        if len(prompt) // 4 > self.summary_input_tokens:
            raise CompactionError("Projected history and reference catalog exceed summary input budget")
        return prompt, catalog

    def _validated_summary(self, response: Any, catalog: dict[str, dict[str, Any]]) -> str:
        meta = response.response_metadata or {}
        if meta.get("stop_reason") == "max_tokens" or meta.get("finish_reason") in {"length", "max_tokens"}:
            raise CompactionError("Summary generation was truncated")
        if response.tool_calls or response.invalid_tool_calls:
            raise CompactionError("Summarizer returned tool calls")
        try:
            text = response.text.strip()
            if text.startswith("```json") and text.endswith("```"):
                text = text[7:-3].strip()
            result = json.loads(text)
            narrative, keys = result["summary"], result["retained_reference_keys"]
            if not isinstance(narrative, str) or not narrative.strip() or not isinstance(keys, list):
                raise ValueError("invalid schema")
            if any(not isinstance(key, str) or key not in catalog for key in keys):
                raise ValueError("unknown reference key")
            if "Previous conversation was too long" in narrative or "No previous conversation history" in narrative:
                raise ValueError("placeholder summary")
            # Model prose is not an executable reference channel.
            narrative = _strip_manifest(narrative)
            if not narrative.strip():
                raise ValueError("empty narrative")
        except (ValueError, TypeError, KeyError) as exc:
            raise CompactionError("Invalid summary or reference selection") from exc
        selected = [catalog[key] for key in dict.fromkeys(keys)]
        mandatory = [c for c in catalog.values() if c.get("required")]
        selected += [c for c in mandatory if c["key"] not in keys]
        # Selected build/RFQ references require their exact fixing dependencies.
        # Unselected optional builds do not pin every historical market snapshot.
        for parent in list(selected):
            for ref in parent.get("reference", {}).get("summary", {}).get("fixing_references", []):
                key = f"artifact:{ref['artifact_id']}"
                if key not in catalog:
                    raise CompactionError("Selected fixing dependency is unavailable")
                if not any(c["key"] == key for c in selected):
                    selected.append(catalog[key])
        text = narrative.strip()
        if selected:
            manifest = _render_disclosure(selected)
            if _text_tokens(manifest) > self.reference_tokens:
                raise CompactionError("Selected references exceed reference budget")
            text += "\n" + manifest
        if _text_tokens(text) > self.retained_tokens:
            raise CompactionError("Summary and selected references exceed retained-context budget")
        return _Summary(text, selected)

    def _build_new_messages_with_path(self, summary: str, file_path: str | None):
        messages = super()._build_new_messages_with_path(summary, file_path)
        messages[0].additional_kwargs["disclosure_references"] = getattr(summary, "references", [])
        state = _REQUEST_STATE.get()
        controls = {"todos": state.get("todos", [])}
        # Preserve the latest real instruction independently of model prose.
        for message in reversed(state.get("messages", [])):
            if isinstance(message, HumanMessage) and not self._is_summary_message(message):
                controls["current_instruction"] = message.text
                break
        if controls.get("todos") or controls.get("current_instruction"):
            messages[0].content += "\n<current_work>\n" + json.dumps(controls, ensure_ascii=False) + "\n</current_work>"
        if _text_tokens(messages[0].text) > self.retained_tokens:
            raise CompactionError("Summary wrapper and current work exceed retained-context budget")
        return messages

    def _remember_attempt(self, messages):
        attempt = _ATTEMPT.get()
        if attempt is not None:
            # DeepAgents gathers summary and offload in child asyncio tasks.
            # ContextVar assignments there do not propagate to the parent;
            # update this request-local sink shared by those tasks instead.
            attempt.update(prefix_length=len(messages), identity=self._attempt_identity(messages))

    def _attempt_identity(self, messages):
        projected, references = project_compaction_messages(messages)
        state = _REQUEST_STATE.get()
        instruction = next((m.text for m in reversed(state.get("messages", []))
                            if isinstance(m, HumanMessage) and not self._is_summary_message(m)), "")
        required = [c for c in _scoped_catalog().values() if c.get("required")]
        payload = {"prefix": get_buffer_string(projected, format="xml"), "references": references,
                   "required": required, "instruction": instruction, "todos": state.get("todos", []),
                   "budgets": [self.summary_input_tokens, self.summary_output_tokens, self.retained_tokens, self.reference_tokens],
                   "summary_config": getattr(getattr(self._summary_runner, "bound", None), "_identifying_params", {}),
                   "prompt": LEDGER_AWARE_SUMMARY_PROMPT}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    def _previous_attempt_failed(self, request):
        failure = request.state.get("_compaction_failure") or {}
        messages = self._get_effective_messages(request)
        n = failure.get("prefix_length")
        return (isinstance(n, int) and 0 < n <= len(messages)
                and failure.get("identity") == self._attempt_identity(messages[:n]))

    def wrap_model_call(self, request, handler):
        token = _REQUEST_STATE.set(request.state)
        attempt_token = _ATTEMPT.set({})
        try:
            request = request.override(messages=self._capture_long_messages(request.messages))
            if self._previous_attempt_failed(request):
                return self._without_compaction(request, handler)
            def checked(reduced):
                self._validate_reduction(request, reduced)
                return handler(reduced)
            try:
                return super().wrap_model_call(request, checked)
            except CompactionError as exc:
                response = self._without_compaction(request, handler)
                return ExtendedModelResponse(model_response=response, command=Command(update={
                    "_compaction_failure": {**(_ATTEMPT.get() or {}), "reason": str(exc)},
                }))
        finally:
            _REQUEST_STATE.reset(token)
            _ATTEMPT.reset(attempt_token)

    async def awrap_model_call(self, request, handler):
        token = _REQUEST_STATE.set(request.state)
        attempt_token = _ATTEMPT.set({})
        try:
            import asyncio
            captured = await asyncio.to_thread(self._capture_long_messages, request.messages)
            request = request.override(messages=captured)
            if self._previous_attempt_failed(request):
                return await self._awithout_compaction(request, handler)
            async def checked(reduced):
                self._validate_reduction(request, reduced)
                return await handler(reduced)
            try:
                return await super().awrap_model_call(request, checked)
            except CompactionError as exc:
                response = await self._awithout_compaction(request, handler)
                return ExtendedModelResponse(model_response=response, command=Command(update={
                    "_compaction_failure": {**(_ATTEMPT.get() or {}), "reason": str(exc)},
                }))
        finally:
            _REQUEST_STATE.reset(token)
            _ATTEMPT.reset(attempt_token)

    def _validate_reduction(self, original, reduced):
        before = self._get_effective_messages(original)
        if reduced.messages and self._is_summary_message(reduced.messages[0]) and reduced.messages[0] is not (before[0] if before else None):
            if _count_tokens_approximately(reduced.messages) >= _count_tokens_approximately(before):
                raise CompactionError("Compaction did not reduce context")

    def _without_compaction(self, request, handler):
        effective = request.override(messages=self._get_effective_messages(request))
        self._check_reduction(effective, effective, None)
        return handler(effective)

    async def _awithout_compaction(self, request, handler):
        effective = request.override(messages=self._get_effective_messages(request))
        self._check_reduction(effective, effective, None)
        return await handler(effective)

    async def compact_state(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Explicit user compaction: checkpoint update only, no business model call."""
        token = _REQUEST_STATE.set(state)
        try:
            messages = self._apply_event_to_messages(self._capture_long_messages(state.get("messages", [])),
                                                    state.get("_summarization_event"))
            cutoff = self._determine_cutoff_index(messages)
            if cutoff <= 0:
                return None
            summary = await self._acreate_summary(messages[:cutoff])
            session_id = self._get_session_id(state)
            # Manual compaction runs outside a graph superstep. Save the same
            # DeepAgents XML history in the checkpoint's files channel.
            path = self._get_history_path(session_id)
            from deepagents.backends.utils import create_file_data
            files = state.get("files") or {}
            previous = files.get(path, {}).get("content", "")
            if isinstance(previous, list):
                previous = "\n".join(previous)
            history_messages = self._filter_summary_messages(messages[:cutoff])
            # Outside the graph there is no backend superstep to offload inline
            # media. Refuse loss of an image/document instead of emitting a
            # history pointer whose serializer silently omits its bytes.
            from deepagents.middleware.summarization import _extract_data_url
            if any(_extract_data_url(block) for m in history_messages for block in m.content_blocks):
                raise CompactionError("Inline media must be saved before manual compaction")
            history = get_buffer_string(history_messages, format="xml")
            file = create_file_data(previous + "\n" + history)
            kept = [*self._build_new_messages_with_path(summary, path), *messages[cutoff:]]
            if _count_tokens_approximately(kept) >= _count_tokens_approximately(messages):
                raise CompactionError("Compaction did not reduce context")
            return {"_summarization_event": {
                "cutoff_index": self._compute_state_cutoff(state.get("_summarization_event"), cutoff),
                "summary_message": kept[0], "file_path": path,
            }, "_summarization_session_id": session_id, "files": {path: file}, "_compaction_failure": None}
        finally:
            _REQUEST_STATE.reset(token)

    def _capture_long_messages(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """Persist report/plan bodies before replacing them with selected cards.

        Capture occurs only within an attributed run; standalone unit/benchmark
        messages have their own exact evidence fixtures. CAS deduplicates retries.
        """
        from .artifact_access import _active_config
        config = _REQUEST_CONFIG.get()
        values = _active_config(config)
        raw_thread = values.get("parent_thread_id") or values.get("thread_id")
        if not values.get("workflow_id") and not str(raw_thread).isdigit():
            return messages
        from .cas_backend import ContentAddressedFilesystemBackend
        backend = ContentAddressedFilesystemBackend()
        captured = []
        for message in messages:
            if (not isinstance(message, AIMessage) or self._is_summary_message(message)
                    or _message_artifact_ref(message) is not None
                    or (len(message.text) < 4000 and _message_artifact_kind(message) not in PROTECTED_ARTIFACT_KINDS)):
                captured.append(message)
                continue
            digest = hashlib.sha256(message.text.encode()).hexdigest()
            try:
                ref = backend.capture_tool_result(tool_call_id=f"report-{digest[:32]}",
                    tool_name="assistant_report", content=message.text, tool_args=None,
                    config=config, classification="assistant_report")
            except Exception:
                # Normal execution can continue with the original body. Mark
                # it protected so a later compaction cannot discard it unsaved.
                captured.append(message.model_copy(update={"additional_kwargs": {
                    **message.additional_kwargs, "artifact_kind": "report",
                }}))
                continue
            captured.append(message.model_copy(update={"additional_kwargs": {
                **message.additional_kwargs, "artifact_ref": ref,
                "artifact_ref_provenance": ARTIFACT_REFERENCE_PROVENANCE,
            }}))
        return captured


def _requires_model_profile(trigger: Any) -> bool:
    triggers = trigger if isinstance(trigger, list) else [trigger]
    return any(
        isinstance(item, tuple) and len(item) >= 1 and item[0] == "fraction"
        for item in triggers
    )


def _has_model_profile(model: Any) -> bool:
    profile = getattr(model, "profile", None)
    if profile is None:
        return False
    if isinstance(profile, dict):
        return bool(profile.get("max_input_tokens"))
    return bool(getattr(profile, "max_input_tokens", None))


def _count_tokens_approximately(messages: list[Any], **_kwargs: Any) -> int:
    from langchain_core.messages.utils import count_tokens_approximately
    # LangChain counts text, tool-call arguments and schemas without mistaking
    # opaque signatures for text tokens. Input-wire signatures remain intact.
    counted = []
    for message in messages:
        if not isinstance(message, BaseMessage):
            counted.append(message)
            continue
        content = copy.deepcopy(message.content)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block.pop("signature", None)
                    extras = block.get("extras")
                    if isinstance(extras, dict):
                        extras.pop("signature", None)
        counted_message = message.model_copy(update={"content": content})
        counted.append(counted_message)
    count = count_tokens_approximately(counted, **_kwargs)
    # Standardized content lists may omit tool_use blocks even though tool_calls
    # are stored separately. The library assumes such calls are already in lists.
    for message in counted:
        if isinstance(message, AIMessage) and isinstance(message.content, list) and message.tool_calls:
            if not any(isinstance(b, dict) and b.get("type") in {"tool_use", "tool_call"} for b in message.content):
                count += len(json.dumps(message.tool_calls, default=str)) // 4
        if isinstance(message, AIMessage):
            for key in ("reasoning_content",):
                value = message.additional_kwargs.get(key)
                if isinstance(value, str):
                    count += len(value) // 4
    return count


def _text_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def _visible_card(card: dict[str, Any]) -> dict[str, Any]:
    """Navigation only. Full evidence remains server-owned and rehydratable."""
    ref = card.get("reference") or {}
    visible = {"key": card["key"], "kind": card["kind"],
               "summary": str(card.get("summary") or ref.get("tool_name") or card["kind"])[:160]}
    if card["kind"] == "artifact":
        visible.update(artifact_id=ref["artifact_id"], locator=ref["locator"])
        if ref.get("summary", {}).get("fixing_references"):
            visible["fixing_artifact_ids"] = [r["artifact_id"] for r in ref["summary"]["fixing_references"]]
    elif card["kind"] == "task":
        visible.update(task_id=card["task_id"], status=card.get("status"),
                       output_artifact_id=card.get("output_artifact_id"), depends_on=card.get("depends_on", []))
    else:
        visible.update(record_id=card["record_id"], source_artifact_id=card.get("source_artifact_id"))
    return visible


def _render_disclosure(cards: list[dict[str, Any]]) -> str:
    return ("<disclosure_manifest>\n" + json.dumps([_visible_card(c) for c in cards], ensure_ascii=False,
                                                     separators=(",", ":")) + "\n</disclosure_manifest>\n" + DISCLOSURE_METHODS)


def _strip_manifest(text: str) -> str:
    return re.sub(r"<(artifact_manifest|artifact_ref|disclosure_manifest|current_work)\b[^>]*>.*?</\1>", "", text,
                  flags=re.DOTALL | re.IGNORECASE).strip()


def _artifact_card(reference: dict[str, Any]) -> dict[str, Any]:
    structural = reference.get("summary") or {}
    details = {k: structural[k] for k in ("status", "representation", "output_representation", "ids", "counts") if k in structural}
    short = reference.get("tool_name") or reference.get("title") or reference.get("kind")
    if details:
        short = f"{short}: {json.dumps(details, ensure_ascii=False, separators=(',', ':'))}"
    return {"key": f"artifact:{reference['artifact_id']}", "kind": "artifact",
            "summary": short[:160],
            "reference": reference,
            "retrieve": "inspect_artifact(artifact_id), then read_artifact(artifact_id, returned section or json_pointer, offset, limit)"}


def _summary_runner(model: Any, settings: Any):
    fields = getattr(type(model), "model_fields", {})
    overrides: dict[str, Any] = {}
    for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
        if key in fields:
            overrides[key] = settings.agent_compaction_summary_output_tokens
            break
    if "output_config" in fields:
        overrides["output_config"] = {**(getattr(model, "output_config", None) or {}),
                                      "effort": settings.agent_compaction_summary_effort}
    elif "reasoning_effort" in fields and getattr(model, "reasoning_effort", None):
        overrides["reasoning_effort"] = settings.agent_compaction_summary_effort
    if "extra_body" in fields:
        body = copy.deepcopy(getattr(model, "extra_body", None) or {})
        if "reasoning_effort" in body:
            body["reasoning_effort"] = settings.agent_compaction_summary_effort
            overrides["extra_body"] = body
    # Respect provider-specific model classes; only supported named fields change.
    summary_model = model.model_copy(update=overrides) if overrides else model
    return summary_model.with_retry(stop_after_attempt=2)


def _scoped_catalog() -> dict[str, dict[str, Any]]:
    """Compact current-workflow catalog; never returns task/report/RFQ bodies."""
    from .artifact_access import _active_config, artifact_descriptor
    from app import database
    from app.models import AgentTask, SessionArtifact
    values = _active_config(_REQUEST_CONFIG.get())
    workflow_id = values.get("workflow_id")
    if workflow_id is None:
        raw_thread = values.get("parent_thread_id") or values.get("thread_id")
        if not str(raw_thread).isdigit():
            return {}
        from app.models import Workflow
        with database.SessionLocal() as session:
            workflows = session.query(Workflow.id).filter(Workflow.thread_id == int(raw_thread),
                                                         Workflow.intent == "workspace_meta").all()
            if not workflows:
                return {}
            workflow_id = workflows[0][0]
    catalog: dict[str, dict[str, Any]] = {}
    with database.SessionLocal() as session:
        # Full inventory remains discoverable through list_artifacts. Include
        # recent cards plus pinned and unfinished-task dependency outputs.
        tasks = session.query(AgentTask).filter(AgentTask.workflow_id == int(workflow_id)).all()
        active = [t for t in tasks if t.status not in {"completed", "failed", "cancelled"}]
        required_outputs = {t.output_artifact_id for t in tasks
                            if any(t.id in (a.depends_on or []) for a in active)} - {None}
        artifacts = session.query(SessionArtifact).filter(SessionArtifact.workflow_id == int(workflow_id))
        rows = artifacts.order_by(SessionArtifact.id.desc()).limit(20).all()
        rows += artifacts.filter((SessionArtifact.pinned.is_(True)) |
                                 (SessionArtifact.id.in_(required_outputs))).all()
        for a in rows:
            ref = artifact_descriptor(a)
            card = _artifact_card(ref)
            card["required"] = a.pinned or a.id in required_outputs
            catalog[card["key"]] = card
        # A fixing dependency is carried by typed provenance even when its
        # snapshot is older than the recent inventory. Resolve only in scope.
        fixing_ids = {r["artifact_id"] for c in catalog.values()
                      for r in c.get("reference", {}).get("summary", {}).get("fixing_references", [])}
        for aid in fixing_ids:
            a = session.get(SessionArtifact, aid)
            if a is not None and a.workflow_id == int(workflow_id):
                card = _artifact_card(artifact_descriptor(a))
                card["required"] = any(c.get("required") for c in catalog.values()
                    if aid in [r["artifact_id"] for r in c.get("reference", {}).get("summary", {}).get("fixing_references", [])])
                catalog[card["key"]] = card
        for task in tasks:
            card = {"key": f"task:{task.id}", "kind": "task", "task_id": task.id,
                    "summary": f"{task.task_type}: {task.status}", "status": task.status,
                    "output_artifact_id": task.output_artifact_id,
                    "depends_on": task.depends_on or [], "required": task in active,
                    "retrieve": "read_saved_record(kind='task', record_id=task_id, json_pointer, offset, limit)"}
            catalog[card["key"]] = card
    # DB entity references are backed by workflow artifact receipts, not model
    # prose. Their exact contents are retrieved later by a scoped tool.
    for card in list(catalog.values()):
        ref = card.get("reference", {})
        ids = ref.get("summary", {}).get("ids", {})
        for field, kind in (("rfq_id", "rfq"), ("task_id", "task_run")):
            record_id = ids.get(field)
            if not isinstance(record_id, int) or isinstance(record_id, bool):
                continue
            key = f"{kind}:{record_id}"
            catalog[key] = {"key": key, "kind": kind, "record_id": record_id,
                            "summary": f"Saved {kind}; source artifact {ref['artifact_id']}",
                            "source_artifact_id": ref["artifact_id"],
                            "retrieve": f"read_saved_record(kind='{kind}', record_id={record_id}, json_pointer, offset, limit)"}
    return catalog
