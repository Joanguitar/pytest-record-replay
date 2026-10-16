"""Internal recording state and mutable-argument replay helpers."""

from collections.abc import (
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Sequence,
)
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Callable, List, Optional, Generator, Union, overload
from unittest.mock import patch

import dill

from pytest_record_replay.typing import P, R, R_, T, Call

_recording = False
_recording_context: ContextVar[Optional[bool]] = ContextVar(
    "pytest_record_replay_recording", default=None
)
timestamp = datetime.now().isoformat().replace(":", "-")
_calls_context: ContextVar[Optional[List[Call]]] = ContextVar(
    "pytest_record_replay_set_calls", default=None
)


def recording() -> bool:
    """Return the active recording mode.

    A context-local mode set by :func:`record` takes precedence over the
    session-wide mode configured by the pytest plugin.
    """
    context_recording = _recording_context.get()
    return _recording if context_recording is None else context_recording


@contextmanager
def record(recording_value: bool) -> Generator[bool, None, None]:
    """Temporarily set the context-local recording mode.

    The previous context-local mode is restored when the context exits,
    including when its body raises an exception.
    """
    token = _recording_context.set(recording_value)
    try:
        yield recording_value
    finally:
        _recording_context.reset(token)


@contextmanager
def set_calls(calls: Optional[List[Call]] = None) -> Generator[List[Call], None, None]:
    calls = [] if calls is None else calls
    token = _calls_context.set(calls)
    try:
        yield calls
    finally:
        _calls_context.reset(token)


def get_calls() -> List[Call]:
    calls = _calls_context.get()
    if calls is None:
        raise RuntimeError(
            "get_calls called outside set_calls context. Did you forget to use @set_replay?"
        )
    return calls


def _configure_patch(record: bool):
    """Set the session-wide recording mode used outside ``record`` contexts."""
    global _recording
    _recording = record


def _for_update(arg: R, rarg: R) -> Optional[R]:
    """Capture how to restore ``arg`` to its post-call value ``rarg``.

    Returns ``None`` when the serialized values are equal. For mutable
    containers, returns a deep copy of the post-call state. For non-string
    sequences and mappings, recursively captures updates to their contents.

    Raises:
        TypeError: If the values have different types or a changed value
            cannot be represented as an update.
        ValueError: If ``arg`` cannot be serialized with dill.
    """
    if type(arg) is not type(rarg):
        raise TypeError(
            f"Cannot update mutable argument of type {type(arg).__name__} with {type(rarg).__name__}."
        )
    if not dill.pickles(arg, exact=True):
        raise ValueError(f"Argument {arg} is not picklable.")
    if dill.dumps(arg) == dill.dumps(rarg):
        return None
    if isinstance(arg, (MutableSequence, MutableMapping, MutableSet)):
        return dill.copy(rarg)
    if isinstance(arg, Sequence) and not isinstance(arg, (str, bytes, bytearray)):
        return type(arg)(_for_update(item, ritem) for item, ritem in zip(arg, rarg))  # type: ignore
    if isinstance(arg, Mapping):
        return type(arg)({k: _for_update(v, rarg[k]) for k, v in arg.items()})  # type: ignore
    raise TypeError(f"Cannot update mutable argument of type {type(arg).__name__}.")


def _update_argument(target: R, updated: Optional[R]) -> None:
    """Apply captured post-call state to a replayed argument in place.

    ``None`` indicates that the value was unchanged. Mutable containers are
    updated directly, while immutable containers are traversed to update any
    mutable values nested inside them.

    Raises:
        TypeError: If the saved state has a different type or cannot be applied
            to the target.
    """
    if updated is None:
        return
    if type(target) is not type(updated):
        raise TypeError(
            f"Cannot update mutable argument of type {type(target).__name__} with {type(updated).__name__}."
        )
    if isinstance(target, MutableSequence):
        assert isinstance(updated, MutableSequence)
        target.clear()
        target.extend(updated)
        return
    if isinstance(target, MutableMapping):
        assert isinstance(updated, MutableMapping)
        target.clear()
        target.update(updated)
        return
    if isinstance(target, MutableSet):
        assert isinstance(updated, MutableSet)
        target.clear()
        target |= updated
        return
    if isinstance(target, Sequence) and not isinstance(target, (str, bytes, bytearray)):
        assert isinstance(updated, Sequence)
        for target_item, updated_item in zip(target, updated):
            _update_argument(target_item, updated_item)
        return
    if isinstance(target, Mapping):
        assert isinstance(updated, Mapping)
        for key, value in target.items():
            _update_argument(value, updated[key])
        return
    raise TypeError(f"Cannot update mutable argument of type {type(target).__name__}.")


def none_xor(a, b):
    """Select a value while rejecting conflicting non-None values.

    If either argument is ``None``, return the other. If both are non-None
    and equal, return ``a``; if they differ, raise ``ValueError``.
    """
    if a is None:
        return b
    elif b is None:
        return a
    elif b == a:
        return a
    else:
        raise ValueError("FunctionWCalls already has a record mode.")


def _decorate_class(obj: type, func: Callable[[Callable[P, R]], R_]) -> type:
    """Apply ``func`` to each callable test method on ``obj``."""
    for attr in dir(obj):
        if not attr.startswith(patch.TEST_PREFIX):
            continue

        attr_value = getattr(obj, attr)
        if not hasattr(attr_value, "__call__"):
            continue

        setattr(obj, attr, func(attr_value))

    return obj


def _allow_class(
    func: Callable[[Callable[P, R]], R_],
):
    """Adapt a function decorator to classes by decorating their test methods."""

    @overload
    def wrapped(obj: T) -> T: ...
    @overload
    def wrapped(obj: Callable[P, R]) -> R_: ...
    def wrapped(obj: Union[type, Callable[P, R]]) -> Union[type, R_]:
        if isinstance(obj, type):
            return _decorate_class(obj, func)
        return func(obj)

    return wrapped
