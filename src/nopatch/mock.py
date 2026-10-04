"""Callable recording and replay primitives."""

import importlib
import inspect
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from functools import wraps
from typing import (
    Any,
    Callable,
    Hashable,
    List,
    Optional,
    Tuple,
    ParamSpec,
    TypeVar,
    Generic,
)
from unittest.mock import MagicMock, Mock, NonCallableMock, patch
from typing_extensions import TypeAlias
import unittest

_Params = ParamSpec("_Params")
_RType = TypeVar("_RType")


@dataclass(frozen=True)
class _Call:
    target: str
    args: tuple
    kwargs: dict
    output: Any


RecordableCallable: TypeAlias = Callable[[Hashable, ...], Hashable]
_record_mode = False


def _configure_patch(record: bool):
    """Configure the patching behavior for the current test session."""
    global _record_mode
    _record_mode = record


class NoMockBase(ABC, Mock):
    """Base class for recording and replaying function calls."""

    def __init__(
        self, target: str, *args, calls: Optional[List[_Call]] = None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._target = target
        self._calls = calls if calls is not None else []

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
        output = self.function(*args, **kwargs)
        self._calls.append(
            _Call(target=self._target, args=args, kwargs=kwargs, output=output)
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
        return call.output


class FunctionWCalls(Generic[_Params]):
    """Wrap a test function to have calls attribute."""

    def __init__(
        self,
        function: Callable[_Params, None],
        record: bool = False,
        calls: Optional[List[_Call]] = None,
    ):
        self.func = function
        self.calls: List[_Call] = calls if calls is not None else []
        self.record: bool = record

    def __call__(self, *args: _Params.args, **kwargs: _Params.kwargs) -> None:
        if self.record:
            self._call_record(*args, **kwargs)
        else:
            self._call_recall(*args, **kwargs)

    def _call_record(self, *args: _Params.args, **kwargs: _Params.kwargs):
        assert len(self.calls) == 0, "Calls should be empty before recording."
        self.calls.clear()
        self.func(*args, **kwargs)
        self.save(datetime.now().isoformat())

    def _call_recall(self, *args: _Params.args, **kwargs: _Params.kwargs):
        files = self.files
        assert len(files) > 0, "No recorded calls found."
        for ii, file in enumerate(files):
            self._load_file(file)
            if ii > 0:
                self._TestCaseReset()
            self.func(*args, **kwargs)
            assert len(self.calls) == 0, f"Unconsumed calls remain after replaying {file}."

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
        path = Path(inspect.getfile(self.func))
        path = path.parent / "resources_nopatch" / path.stem
        # If the function is a method, include the class name in the file path
        if inspect.ismethod(self.func):
            path = path / self.func.__self__.__class__.__name__
        path = path / self.func.__name__
        return path

    @property
    def files(self) -> List[Path]:
        """Return a list of files containing the calls."""
        return sorted(self.path.glob("*.json"))

    def _save_file(self, file: Path):
        """Save the calls to a file."""
        with open(file, "w") as f:
            import json

            json.dump([call.__dict__ for call in self.calls], f, default=str)

    def _load_file(self, file: Path):
        """Load the calls from a file."""
        with open(file, "r") as f:
            import json

            calls_data = json.load(f)
            self.calls.clear()
            self.calls.extend(
                _Call(
                    **{**call_data, "args": tuple(call_data["args"])}
                )
                for call_data in calls_data
            )

    def save(self, name: str):
        """Save the calls to a file."""
        self.path.mkdir(parents=True, exist_ok=True)
        file = self.path / (name + ".json")
        self._save_file(file)


def nodecorator(
    record: None | bool = None,
) -> Callable[[Callable[_Params, None]], FunctionWCalls[_Params]]:
    """Return the function without any decoration."""
    if record is None:
        record = _record_mode

    def wrapper(func: Callable[_Params, None]) -> FunctionWCalls[_Params]:
        if isinstance(func, FunctionWCalls):
            raise ValueError(
                "@nodecorator should be applied before any @nopatch decorator."
            )
        return wraps(func)(FunctionWCalls(func, record=record))

    return wrapper


def nopatch(target: str):
    def wrapper(func: FunctionWCalls[_Params]) -> FunctionWCalls[_Params]:
        if not isinstance(func, FunctionWCalls):
            func = nodecorator()(func)
        calls = func.calls
        if func.record:
            patched_func, _ = patch(target).get_original()
            _func = patch(target, NoMockRecord(target, patched_func, calls=calls))(
                func.func
            )
        else:
            _func = patch(target, NoMockRecall(target, calls=calls))(func.func)
        return FunctionWCalls(_func, record=func.record, calls=calls)
    return wrapper
