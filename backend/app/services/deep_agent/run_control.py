"""Process-local LangGraph RunControl registry."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from langgraph.runtime import RunControl


_ASYNC_TASK_CONTROLS: dict[int, RunControl] = {}
_CHECKPOINT_OPERATIONS: set[str] = set()
_LOCK = Lock()


@contextmanager
def checkpoint_operation(key: str) -> Iterator[None]:
    """Serialize manual compaction with streaming on this checkpoint."""
    with _LOCK:
        if key in _CHECKPOINT_OPERATIONS:
            raise RuntimeError("Conversation is busy; wait for the current turn to finish")
        _CHECKPOINT_OPERATIONS.add(key)
    try:
        yield
    finally:
        with _LOCK:
            _CHECKPOINT_OPERATIONS.discard(key)


def new_run_control() -> RunControl:
    return RunControl()


def request_drain(control: RunControl | None, reason: str) -> bool:
    if control is None:
        return False
    control.request_drain(reason=reason)
    return True


@contextmanager
def register_async_task_control(
    task_id: int,
    control: RunControl,
) -> Iterator[RunControl]:
    with _LOCK:
        _ASYNC_TASK_CONTROLS[task_id] = control
    try:
        yield control
    finally:
        with _LOCK:
            if _ASYNC_TASK_CONTROLS.get(task_id) is control:
                _ASYNC_TASK_CONTROLS.pop(task_id, None)


def request_async_task_drain(task_id: int, reason: str = "cancelled") -> bool:
    with _LOCK:
        control = _ASYNC_TASK_CONTROLS.get(task_id)
    return request_drain(control, reason)
