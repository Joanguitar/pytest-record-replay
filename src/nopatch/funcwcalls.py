
from functools import wraps
import inspect
from pathlib import Path
from typing import Any, Callable, Generic, List, Literal, Optional, overload
import unittest
from unittest.mock import patch
import warnings

import dill

from nopatch.typing import Call, P, R
from nopatch.util import recording, timestamp


class FunctionWCalls(Generic[P, R]):
    """Wrap a test function to have calls attribute."""

    @overload
    def __new__(
        cls,
        function: Callable[P, Any],
        *,
        record: Literal[False] = ...,
        calls: None = ...,
        file: None = ...,
    ) -> FunctionWCalls[P, None]: ...

    @overload
    def __new__(
        cls,
        function: Callable[P, R],
        *,
        file: Path,
        record: bool = ...,
        calls: Optional[List[Call]] = ...,
    ) -> FunctionWCalls[P, R]: ...

    @overload
    def __new__(
        cls,
        function: Callable[P, R],
        *,
        calls: List[Call],
        record: bool = ...,
        file: Optional[Path] = ...,
    ) -> FunctionWCalls[P, R]: ...

    @overload
    def __new__(
        cls,
        function: Callable[P, R],
        *,
        record: Literal[True],
        file: Optional[Path] = ...,
        calls: Optional[List[Call]] = ...,
    ) -> FunctionWCalls[P, R]: ...

    def __new__(
        cls,
        function: Callable[P, Any],
        *,
        record: bool = False,
        calls: Optional[List[Call]] = None,
        file: Optional[Path] = None,
    ) -> FunctionWCalls[P, Any]:
        return super().__new__(cls)

    def __init__(
        self,
        function: Callable,
        *,
        record: bool = False,
        calls: Optional[List[Call]] = None,
        file: Optional[Path] = None,
    ):
        self.func = function
        self.record: bool = record
        self.calls: List[Call] = calls if calls is not None else []
        if len(self.calls) > 0:
            if self.record:
                raise ValueError("Calls should be empty when recording.")
            if file is not None:
                warnings.warn("Both calls and file provided. Using calls.")
        self.file = file

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if self.record:
            return self._call_record(*args, **kwargs)
        else:
            return self._call_recall(*args, **kwargs)

    def _call_record(self, *args: P.args, **kwargs: P.kwargs) -> R:
        assert len(self.calls) == 0, "Calls should be empty before recording."
        output = self.func(*args, **kwargs)
        if self.file is None:
            self.save(timestamp)
        else:
            self._save_file(self.file)
        return output

    def _call_recall(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if len(self.calls) > 0:
            return self._call_recall_calls(*args, **kwargs)
        if self.file is not None:
            return self._call_recall_file(*args, **kwargs)
        return self._call_recall_files(*args, **kwargs)

    def _call_recall_calls(
        self, *args: P.args, **kwargs: P.kwargs
    ) -> R:
        output = self.func(*args, **kwargs)
        assert len(self.calls) == 0, (
            f"Unconsumed calls remain after replaying {self.calls}."
        )
        return output

    def _call_recall_file(
        self, *args: P.args, **kwargs: P.kwargs
    ) -> R:
        assert self.file is not None
        self._load_file(self.file)
        return self._call_recall_calls(*args, **kwargs)

    def _call_recall_files(
        self, *args: P.args, **kwargs: P.kwargs
    ) -> R:  # type: ignore
        files = self.files
        assert len(files) > 0, "No recorded calls found."
        for ii, file in enumerate(files):
            self._load_file(file)
            if ii > 0:
                self._TestCaseReset()
            self._call_recall_calls(*args, **kwargs)

    def _TestCaseReset(self) -> bool:
        """Calls tearDown/setUp method if the function is a method of a TestCase."""
        if hasattr(self.func, "__self__"):
            testcase = self.func.__self__  # type: ignore
            if isinstance(testcase, unittest.TestCase):
                testcase.tearDown()
                testcase.setUp()
                return True
        return False

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


def has_funcwcalls(func: Callable) -> bool:
    return hasattr(func, "function_with_calls") and isinstance(
        func.function_with_calls,  # type: ignore
        FunctionWCalls,
    )


def get_funcwcalls(func: Callable) -> FunctionWCalls:
    if not has_funcwcalls(func):
        raise ValueError("Function does not have calls.")
    return func.function_with_calls  # type: ignore


def _set_patched_func(
    func: Callable[P, Optional[R]],
    record: bool,
    calls: Optional[List[Call]],
    file: Optional[Path],
) -> Callable[P, Optional[R]]:
    function_with_calls = wraps(func)(
        FunctionWCalls(func, record=record, calls=calls, file=file)
    )

    @wraps(func)
    def patched_func(*args: P.args, **kwargs: P.kwargs):
        return function_with_calls(*args, **kwargs)

    patched_func.function_with_calls = function_with_calls  # type: ignore
    return patched_func
