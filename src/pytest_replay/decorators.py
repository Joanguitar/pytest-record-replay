"""Decorators for recording and replaying patched dependencies."""

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Optional, Union, overload
from unittest.mock import patch

from pytest_replay.funcwcalls import (
    FunctionWCalls,
    set_funcwcalls,
    get_funcwcalls,
    has_funcwcalls,
)
from pytest_replay.mock import ReplayMockBase, ReplayMock, RecordingMock
from pytest_replay.typing import P, R
from pytest_replay.util import recording


def nodecorator(
    record: Optional[bool] = None, file: Optional[Path] = None
) -> Callable[[Callable[P, R]], Callable[P, Optional[R]]]:
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
    if record is None:
        record = recording()

    def wrapper(
        func: Callable[P, R],
    ) -> Callable[P, Optional[R]]:
        if has_funcwcalls(func):
            raise AttributeError(
                "@nodecorator should be applied before any @replay decorator."
            )
        patched_func = patch("pytest_replay.util.recording", lambda: record)(func)
        return set_funcwcalls(patched_func, record=record, calls=None, file=file)

    return wrapper


def replay_mock(target: str, funcwcalls: FunctionWCalls) -> ReplayMockBase:
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
        return RecordingMock(target, original_func, calls=calls)
    return ReplayMock(target, calls=calls)


@overload
def replay_patch(func: FunctionWCalls[P, R], target: str) -> FunctionWCalls[P, R]: ...
@overload
def replay_patch(
    func: Callable[P, Optional[R]], target: str
) -> Callable[P, Optional[R]]: ...


def replay_patch(
    func: Union[Callable[P, Optional[R]], FunctionWCalls[P, R]],
    target: str,
) -> Union[Callable[P, Optional[R]], FunctionWCalls[P, R]]:
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
    is_function_with_calls = isinstance(func, FunctionWCalls)
    if is_function_with_calls:
        function_with_calls: FunctionWCalls = func
    else:
        if not has_funcwcalls(func):
            func = nodecorator()(func)
        function_with_calls = get_funcwcalls(func)

    wrapped_func = function_with_calls.func
    record = function_with_calls.record
    calls = function_with_calls.calls
    file = function_with_calls.file
    mock = replay_mock(target, function_with_calls)
    patched_func = patch(target, mock)(wrapped_func)

    if is_function_with_calls:
        return FunctionWCalls(patched_func, record=record, calls=calls, file=file)
    return set_funcwcalls(patched_func, record=record, calls=calls, file=file)


def replay(target: str):
    """Return a decorator that records or replays calls to a dependency.

    Args:
        target: The fully qualified name of the dependency to patch.

    Returns:
        A decorator suitable for applying directly to a test function.
    """
    return partial(replay_patch, target=target)
