"""Callable recording and replay primitives."""

import inspect
import unittest
from abc import ABC, abstractmethod
from collections.abc import MutableMapping, MutableSequence, MutableSet, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Generic, List, Optional, Tuple, TypeVar, overload
from unittest.mock import Mock, patch

import dill
from typing_extensions import ParamSpec

_HParams = ParamSpec("_HParams")
_RType = TypeVar("_RType")

_recording = False
timestamp = datetime.now().isoformat().replace(":", "-")


def recording() -> bool:
    return _recording


def _configure_patch(record: bool):
    """Configure the patching behavior for the current test session."""
    global _recording
    _recording = record


@dataclass(frozen=True)
class _Call:
    target: str
    args: tuple
    kwargs: dict
    output: Any
    post_args: Optional[Tuple[Any, ...]] = None
    post_kwargs: Optional[dict] = None


def _can_update(target: Any) -> bool:
    """Check if the target is a mutable collection that can be updated by _update_mutable_argument."""
    if isinstance(target, (MutableSequence, MutableMapping, MutableSet)):
        return True
    if isinstance(target, Sequence) and not isinstance(target, (str, bytes, bytearray)):
        return all(_can_update(item) for item in target)
    return False


def _for_update(arg: _RType, rarg: _RType) -> Optional[_RType]:
    """Return the post-call argument for updating mutable arguments."""
    if type(arg) != type(rarg):
        raise TypeError(
            f"Cannot update mutable argument of type {type(arg).__name__} with {type(rarg).__name__}."
        )
    if not dill.pickles(arg, exact=True):
        raise ValueError(f"Argument {arg} is not picklable.")
    if dill.dumps(arg) == dill.dumps(rarg):
        return None
    if _can_update(arg):
        return dill.copy(rarg)
    raise TypeError(f"Cannot update mutable argument of type {type(arg).__name__}.")


def _update_argument(target: _RType, updated: Optional[_RType]) -> None:
    """Restore any in-place mutations captured after a recorded call."""
    if updated is None:
        return target
    if type(target) != type(updated):
        raise TypeError(
            f"Cannot update mutable argument of type {type(target).__name__} with {type(updated).__name__}."
        )
    if isinstance(target, MutableSequence):
        target.clear()
        target.extend(updated)
        return
    if isinstance(target, (MutableMapping, MutableSet)):
        target.clear()
        target.update(updated)
        return
    if isinstance(target, Sequence) and not isinstance(target, (str, bytes, bytearray)):
        for target_item, updated_item in zip(target, updated):
            _update_argument(target_item, updated_item)
        return
    raise TypeError(f"Cannot update mutable argument of type {type(target).__name__}.")


class NoMockBase(ABC, Mock):
    """Base class for recording and replaying function calls."""

    def __init__(
        self, target: str, *args, calls: Optional[List[_Call]] = None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._target = target
        self._calls = calls if calls is not None else []

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if isinstance(self, NoMockRecord):
            function = self.function.__get__(instance, owner)
            return NoMockRecord(self._target, function, calls=self._calls)
        return NoMockRecall(self._target, calls=self._calls)

    @abstractmethod
    def _execute_mock_call(self, /, *args, **kwargs): ...


class NoMockRecord(NoMockBase):
    """Call a function normally while saving its inputs and output."""

    def __init__(
        self,
        target: str,
        function: Callable,
        *args,
        calls: Optional[List[_Call]] = None,
        **kwargs,
    ):
        super().__init__(target, *args, calls=calls, **kwargs)
        self.function = function

    def _execute_mock_call(self, /, *args, **kwargs):
        # Make sure that the arguments and the output are picklable before recording
        for arg in args:
            if not dill.pickles(arg, exact=True):
                raise ValueError(f"Argument {arg} is not picklable.")
        for key, value in kwargs.items():
            if not dill.pickles(value, exact=True):
                raise ValueError(f"Keyword argument {key}={value} is not picklable.")
        recorded_args = dill.copy(args)
        recorded_kwargs = dill.copy(kwargs)
        output = self.function(*args, **kwargs)
        if not dill.pickles(output, exact=True):
            raise ValueError(f"Output {output} is not picklable.")
        recorded_output = dill.copy(output)
        post_args = tuple(
            _for_update(arg, recorded_arg)
            for arg, recorded_arg in zip(args, recorded_args)
        )
        post_kwargs = {
            key: _for_update(value, recorded_kwargs[key])
            for key, value in kwargs.items()
        }
        self._calls.append(
            _Call(
                target=self._target,
                args=recorded_args,
                kwargs=recorded_kwargs,
                output=recorded_output,
                post_args=post_args,
                post_kwargs=post_kwargs,
            )
        )
        return output


class NoMockRecall(NoMockBase):
    """Replay the outputs recorded by a :class:`NoMockRecord` instance."""

    def __init__(self, target: str, *args, calls: List[_Call] = None, **kwargs):
        super().__init__(target, *args, calls=calls, **kwargs)

    def _execute_mock_call(self, /, *args, **kwargs):
        call = self._calls.pop(0)
        if call.target != self._target:
            raise ValueError(
                f"Target mismatch: expected {call.target}, got {self._target}"
            )
        if call.args != args or call.kwargs != kwargs:
            raise ValueError(
                f"Arguments mismatch: expected {call.args} and {call.kwargs}, got {args} and {kwargs}"
            )
        for arg, post_arg in zip(args, call.post_args):
            _update_argument(arg, post_arg)
        for key, value in kwargs.items():
            _update_argument(value, call.post_kwargs[key])
        return call.output


class FunctionWCalls(Generic[_HParams, _RType]):
    """Wrap a test function to have calls attribute."""

    @overload
    def __init__(
        self,
        function: Callable[_HParams, _RType],
        record: bool = ...,
        calls: Optional[List[_Call]] = ...,
        file: Path = ...,
    ): ...

    @overload
    def __init__(
        self,
        function: Callable[_HParams, _RType],
        record: bool = ...,
        calls: List[_Call] = ...,
        file: Optional[Path] = ...,
    ): ...

    @overload
    def __init__(
        self,
        function: Callable[_HParams, _RType],
        record: bool = ...,
        calls: Optional[List[_Call]] = ...,
        file: None = ...,
    ): ...

    def __init__(
        self,
        function: Callable[_HParams, _RType],
        record: bool = False,
        calls: Optional[List[_Call]] = None,
        file: Optional[Path] = None,
    ):
        self.func = function
        self.record: bool = record
        self.calls: List[_Call] = calls if calls is not None else []
        self.file = file

    def __call__(self, *args: _HParams.args, **kwargs: _HParams.kwargs) -> _RType:
        if self.record:
            return self._call_record(*args, **kwargs)
        else:
            return self._call_recall(*args, **kwargs)

    def _call_record(self, *args: _HParams.args, **kwargs: _HParams.kwargs) -> _RType:
        assert len(self.calls) == 0, "Calls should be empty before recording."
        output = self.func(*args, **kwargs)
        if self.file is None:
            self.save(timestamp)
        else:
            self._save_file(self.file)
        return output

    def _call_recall(self, *args: _HParams.args, **kwargs: _HParams.kwargs):
        if len(self.calls) > 0:
            return self._call_recall_calls(*args, **kwargs)
        if self.file is not None:
            return self._call_recall_file(*args, **kwargs)
        return self._call_recall_files(*args, **kwargs)

    def _call_recall_calls(self, *args: _HParams.args, **kwargs: _HParams.kwargs) -> _RType:
        output = self.func(*args, **kwargs)
        assert len(self.calls) == 0, (
            f"Unconsumed calls remain after replaying {self.calls}."
        )
        return output

    def _call_recall_file(self, *args: _HParams.args, **kwargs: _HParams.kwargs) -> _RType:
        self._load_file(self.file)
        return self._call_recall_calls(*args, **kwargs)

    def _call_recall_files(self, *args: _HParams.args, **kwargs: _HParams.kwargs) -> List[_RType]:
        files = self.files
        assert len(files) > 0, "No recorded calls found."
        outputs = []
        for ii, file in enumerate(files):
            self._load_file(file)
            if ii > 0:
                self._TestCaseReset()
            outputs.append(self._call_recall_calls(*args, **kwargs))
        return outputs

    def _TestCaseReset(self):
        """Calls tearDown/setUp method if the function is a method of a TestCase."""
        if hasattr(self.func, "__self__") and isinstance(
            self.func.__self__, unittest.TestCase
        ):
            self.func.__self__.tearDown()
            self.func.__self__.setUp()

    @property
    def path(self) -> Path:
        """Return a file unique to the function."""
        function = inspect.unwrap(self.func)
        path = Path(inspect.getfile(function))
        path = path.parent / "resources_nopatch" / path.stem
        # If the function is a method, include the class name in the file path
        if inspect.ismethod(function):
            path = path / function.__self__.__class__.__name__
        path = path / function.__name__
        return path

    @property
    def files(self) -> List[Path]:
        """Return a list of files containing the calls."""
        return sorted(self.path.glob("*.pkl"))

    def _save_file(self, file: Path):
        """Save the calls to a file."""
        self.path.mkdir(parents=True, exist_ok=True)
        with open(file, "wb") as f:
            dill.dump(self.calls, f)

    def _load_file(self, file: Path):
        """Load the calls from a file."""
        with open(file, "rb") as f:
            calls_data = dill.load(f)
            self.calls.clear()
            self.calls.extend(calls_data)

    def save(self, name: str):
        """Save the calls to a file."""
        file = self.path / (name + ".pkl")
        self._save_file(file)


def nodecorator(
    record: Optional[bool] = None,
) -> Callable[[Callable[_HParams, None]], Callable[_HParams, None]]:
    """Return the function without any decoration."""
    if record is None:
        record = _recording

    patch_recording = patch(f"{__name__}.recording", Mock(return_value=record))

    def wrapper(func: Callable[_HParams, None]) -> Callable[_HParams, None]:
        if hasattr(func, "function_with_calls") and isinstance(
            func.function_with_calls, FunctionWCalls
        ):
            raise ValueError(
                "@nodecorator should be applied before any @nopatch decorator."
            )
        function_with_calls = wraps(func)(
            FunctionWCalls(patch_recording(func), record=record)
        )

        @wraps(func)
        def patched_function(*args: _HParams.args, **kwargs: _HParams.kwargs):
            return function_with_calls(*args, **kwargs)

        patched_function.function_with_calls = function_with_calls
        return patched_function

    return wrapper


def nopatch(target: str):
    def wrapper(func: Callable[_HParams, None]) -> Callable[_HParams, None]:
        if not (
            hasattr(func, "function_with_calls")
            and isinstance(func.function_with_calls, FunctionWCalls)
        ):
            func = nodecorator()(func)
        function_with_calls: FunctionWCalls = func.function_with_calls
        func = function_with_calls.func
        calls = function_with_calls.calls
        record = function_with_calls.record
        if function_with_calls.record:
            patched_func, _ = patch(target).get_original()
            _func = patch(target, NoMockRecord(target, patched_func, calls=calls))(func)
        else:
            _func = patch(target, NoMockRecall(target, calls=calls))(func)

        function_with_calls = FunctionWCalls(_func, record=record, calls=calls)

        @wraps(func)
        def patched_function(*args: _HParams.args, **kwargs: _HParams.kwargs):
            return function_with_calls(*args, **kwargs)

        patched_function.function_with_calls = function_with_calls
        return patched_function

    return wrapper
