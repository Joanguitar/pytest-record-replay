"""Decorators for recording and replaying patched dependencies."""

from functools import partial, wraps
from pathlib import Path
from typing import Callable, Optional, Union
from unittest.mock import patch

from pytest_record_replay.funcwcalls import (
    FunctionWCalls,
)
from pytest_record_replay.mock import MockRBase, MockReplay, MockRecord
from pytest_record_replay.typing import P, R
from pytest_record_replay.util import recording


def set_replay(
    record: Optional[bool] = None, file: Optional[Path] = None
) -> Callable[[Callable[P, R]], FunctionWCalls[P, Optional[R]]]:
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
    ) -> Union[FunctionWCalls[P, R], FunctionWCalls[P, None]]:
        if isinstance(func, FunctionWCalls):
            raise AttributeError(
                "@set_replay should be applied before any @patch_replay decorator."
            )
        patched_func = patch("pytest_record_replay.util.recording", lambda: record)(
            func
        )
        funcwcalls = FunctionWCalls(patched_func, record=record, calls=None, file=file)
        return funcwcalls

    return wrapper


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
    func: Union[Callable[P, Optional[R]], FunctionWCalls[P, R]],
    target: str,
) -> FunctionWCalls[P, R]:
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

    mock = replay_mock(target, func)

    return func.decorated(patch(target, mock))


def patch_replay(target: str):
    """Return a decorator that records or replays calls to a dependency.

    Args:
        target: The fully qualified name of the dependency to patch.

    Returns:
        A decorator suitable for applying directly to a test function.
    """
    return partial(patcher_replay, target=target)
