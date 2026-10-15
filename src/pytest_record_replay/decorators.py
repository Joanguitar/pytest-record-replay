"""Decorators for recording and replaying patched dependencies."""

from functools import partial
from pathlib import Path
from typing import Callable, Optional, Union, overload
from unittest.mock import patch

from pytest_record_replay.funcwcalls import (
    FunctionWCalls,
)
from pytest_record_replay.mock import MockR
from pytest_record_replay.typing import P, R, R_, T
from pytest_record_replay.util import none_xor


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


def set_replay(record: Optional[bool] = None, file: Optional[Path] = None):
    """Wrap a function with replay call tracking, without patching a dependency.

    Args:
        record: Whether calls should be recorded. If omitted, use the active
            recording mode when the wrapped function is called.
        file: Optional pickle file to write during recording or read during
            replay. If omitted, use the default recordings directory.

    Returns:
        A decorator that wraps the function and exposes its call metadata. It
        can also decorate a class, applying the wrapper to each test method.

    Raises:
        AttributeError: If existing replay metadata has conflicting recording
            mode or file settings.
    """

    def wrapper(
        func: Union[Callable[P, R], FunctionWCalls[P, R]],
    ):
        if isinstance(func, FunctionWCalls):
            _func = func._func
            try:
                _record = none_xor(record, func._record)
                _calls = func.calls
                _file = none_xor(file, func.file)
            except ValueError as e:
                raise AttributeError(
                    "Incompatible set_replay decorator.\n"
                    "Trying to replace:\n"
                    f"record: {record}->{func._record}\n"
                    f"file: {file}->{func.file}\n"
                ) from e
        else:
            _func = func
            _record = record
            _calls = []
            _file = file

        return FunctionWCalls(
            _func,
            record=_record,
            calls=_calls,
            file=_file,
        )

    return _allow_class(wrapper)


def patcher_replay(
    func: Union[Callable[P, R], FunctionWCalls[P, R], FunctionWCalls[P, None]],
    target: str,
):
    """Decorate a function so calls to ``target`` are recorded or replayed.

    Plain functions are first wrapped using the active recording mode.
    Functions already carrying replay metadata retain their recording mode,
    call history, and file. In either case, a new ``FunctionWCalls`` wrapper
    invokes the function with ``target`` patched.

    Args:
        func: The test function to wrap, or its ``FunctionWCalls`` metadata.
        target: The fully qualified name of the dependency to patch.

    Returns:
        The wrapped test function.
    """
    if not isinstance(func, FunctionWCalls):
        func = set_replay()(func)

    return func.decorated(patch(target, MockR(target, calls=func.calls)))


def patch_replay(target: str):
    """Return a decorator that records or replays calls to a dependency.

    Args:
        target: The fully qualified name of the dependency to patch.

    Returns:
        A decorator suitable for applying to a test function or a test class.
        When given a class, the patch is applied to each callable test method.
    """
    _patcher = partial(patcher_replay, target=target)
    return _allow_class(_patcher)
