"""Decorators for recording and replaying patched dependencies."""

from pathlib import Path
from types import TracebackType
from typing import Callable, Optional, Type, Union, overload
from unittest.mock import patch

from pytest_record_replay.funcwcalls import (
    FunctionWCalls,
)
from pytest_record_replay.mock import MockR
from pytest_record_replay.typing import P, R, T
from pytest_record_replay.util import none_xor, _allow_class


def set_replay(
    record: Optional[bool] = None,
    file: Optional[Path] = None,
    path: Optional[Path] = None,
):
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
        func: Callable[P, R],
    ):
        if isinstance(func, FunctionWCalls):
            _func = func._func
            try:
                _record = none_xor(record, func._record)
                _calls = func.calls.copy()
                _file = none_xor(file, func.file)
                _path = none_xor(path, func._path)
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
            _path = path

        return FunctionWCalls(
            _func,
            record=_record,
            calls=_calls,
            file=_file,
            path=_path,
        )

    return _allow_class(wrapper)


class patcher_replay:
    def __init__(self, target: str):
        self.target = target
        self.mock = MockR(self.target)
        self.patch = patch(self.target, self.mock)

    @overload
    def __call__(self, obj: T) -> T: ...
    @overload
    def __call__(
        self, obj: Callable[P, R]
    ) -> Union[FunctionWCalls[P, R], FunctionWCalls[P, None]]: ...

    def __call__(
        self, obj: Union[T, Callable[P, R]]
    ) -> Union[T, FunctionWCalls[P, R], FunctionWCalls[P, None]]:
        @_allow_class
        def __call(obj: Callable[P, R]):
            func = obj if isinstance(obj, FunctionWCalls) else set_replay()(obj)
            return func.decorated(patch(self.target, MockR(self.target)))

        return __call(obj)

    def __enter__(self) -> MockR:
        return self.patch.__enter__()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        return self.patch.__exit__(exc_type, exc_value, traceback)


def patch_replay(target: str):
    """Return a decorator that records or replays calls to a dependency.

    Args:
        target: The fully qualified name of the dependency to patch.

    Returns:
        A decorator suitable for applying to a test function or a test class.
        When given a class, the patch is applied to each callable test method.
    """
    return patcher_replay(target)
