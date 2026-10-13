"""Decorators for recording and replaying patched dependencies."""

from functools import partial
from pathlib import Path
from typing import Callable, Optional, Union, overload
from unittest.mock import patch

from pytest_record_replay.funcwcalls import (
    FunctionWCalls,
)
from pytest_record_replay.mock import MockRBase, MockReplay, MockRecord
from pytest_record_replay.typing import P, R, R_
from pytest_record_replay.util import recording


def _decorate_class(obj: type, func: Callable[[Callable[P, R]], R_]) -> type:
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
) -> Callable[[Union[type, Callable[P, R]]], Union[type, R_]]:
    @overload
    def wrapped(obj: type) -> type: ...
    @overload
    def wrapped(obj: Callable[P, R]) -> R_: ...
    def wrapped(obj: Union[type, Callable[P, R]]) -> Union[type, R_]:
        if isinstance(obj, type):
            _decorate_class(obj, func)
        return func(obj)

    return wrapped


def set_replay(record: Optional[bool] = None, file: Optional[Path] = None):
    """Wrap a function with replay call tracking, without patching a dependency.

    Args:
        record: Whether calls should be recorded. If omitted, use the current
            replay recording mode.
        file: Optional file to use when recording or replaying calls.

    Returns:
        A decorator that wraps the function and exposes its call metadata.

    Raises:
        AttributeError: If the function already has replay call metadata.
    """
    record = recording() if record is None else record

    def wrapper(
        func: Callable[P, R],
    ) -> Union[FunctionWCalls[P, R], FunctionWCalls[P, None]]:
        if isinstance(func, FunctionWCalls):
            raise AttributeError(
                "@set_replay should be applied before any @patch_replay decorator."
            )
        return FunctionWCalls(
            patch("pytest_record_replay.util.recording", lambda: record)(func),
            record=record,
            file=file,
        )

    return _allow_class(wrapper)


def replay_mock(target: str, funcwcalls: FunctionWCalls) -> MockRBase:
    """Create the mock used to record or replay calls to a patched target.

    The mock type is selected from ``funcwcalls.record`` and shares its call
    list, so recorded calls are visible to the wrapped test function.

    Args:
        target: The fully qualified name of the function being patched.
        funcwcalls: The wrapper that contains recording mode and call data.
    """
    calls = funcwcalls.calls
    if funcwcalls.record:
        original_func, _ = patch(target).get_original()
        return MockRecord(target, original_func, calls=calls)
    return MockReplay(target, calls=calls)


def patcher_replay(
    func: Union[Callable[P, R], FunctionWCalls[P, R], FunctionWCalls[P, None]],
    target: str,
):
    """Decorate a function so calls to ``target`` are recorded or replayed.

    Plain functions are first wrapped using the current recording mode.
    Functions already carrying replay metadata keep that configuration. A
    ``FunctionWCalls`` passed directly is returned as a ``FunctionWCalls``.

    Args:
        func: The test function to wrap, or its ``FunctionWCalls`` metadata.
        target: The fully qualified name of the dependency to patch.

    Returns:
        The wrapped test function.
    """
    if not isinstance(func, FunctionWCalls):
        func = set_replay()(func)
        assert not isinstance(func, type)

    return func.decorated(patch(target, replay_mock(target, func)))


def patch_replay(target: str):
    """Return a decorator that records or replays calls to a dependency.

    Args:
        target: The fully qualified name of the dependency to patch.

    Returns:
        A decorator suitable for applying directly to a test function.
    """
    _patcher = partial(patcher_replay, target=target)
    return _allow_class(_patcher)
