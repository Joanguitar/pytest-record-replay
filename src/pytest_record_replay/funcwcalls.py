"""Track test-function calls and persist or replay dependency histories."""

from __future__ import annotations

from functools import wraps
import inspect
from pathlib import Path
from typing import Any, Callable, Generic, List, Literal, Optional, overload
import unittest
import warnings

import dill

from pytest_record_replay.typing import Call, P, R
from pytest_record_replay.util import timestamp


class FunctionWCalls(Generic[P, R]):
    """Wrap a test function with recording, replay, and call-file management.

    In recording mode, the wrapped function runs and its patched calls are
    saved. In replay mode, saved calls are consumed while the function runs.
    Call data may be supplied directly, loaded from ``file``, or discovered
    from this function's default recordings directory.
    """

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
        """Initialize call tracking for ``function``.

        Args:
            function: Test function to invoke while recording or replaying.
            record: If true, save new calls; otherwise replay saved calls.
            calls: Optional call history shared with patched dependency mocks.
            file: Optional explicit recording file.

        Raises:
            ValueError: If recording is requested with a nonempty call history.
        """
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
        """Invoke the wrapped function in the configured mode."""
        if self.record:
            return self._call_record(*args, **kwargs)
        else:
            return self._call_recall(*args, **kwargs)

    def _call_record(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Run the function and persist calls made by patched dependencies."""
        assert len(self.calls) == 0, "Calls should be empty before recording."
        output = self.func(*args, **kwargs)
        if self.file is None:
            self.save(timestamp)
        else:
            self._save(self.file)
        return output

    def _call_recall(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Replay from in-memory calls, an explicit file, or saved files."""
        if len(self.calls) > 0:
            return self._call_recall_calls(*args, **kwargs)
        if self.file is not None:
            return self._call_recall_file(*args, **kwargs)
        return self._call_recall_files(*args, **kwargs)

    def _call_recall_calls(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Run the function against in-memory calls and require full consumption."""
        output = self.func(*args, **kwargs)
        assert len(self.calls) == 0, (
            f"Unconsumed calls remain after replaying {self.calls}."
        )
        return output

    def _call_recall_file(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Load the configured call file, then replay its calls."""
        assert self.file is not None
        self._load(self.file)
        return self._call_recall_calls(*args, **kwargs)

    def _call_recall_files(self, *args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore
        """Replay each saved call file in sorted order."""
        files = self.files
        assert len(files) > 0, "No recorded calls found."
        for ii, file in enumerate(files):
            self._load(file)
            if ii > 0:
                self._TestCaseReset()
            self._call_recall_calls(*args, **kwargs)

    def _TestCaseReset(self) -> bool:
        """Reset a bound ``unittest.TestCase`` between recording files.

        Returns:
            Whether the wrapped function belongs to a ``TestCase`` instance.
        """
        if hasattr(self.func, "__self__"):
            testcase = self.func.__self__  # type: ignore
            if isinstance(testcase, unittest.TestCase):
                testcase.tearDown()
                testcase.setUp()
                return True
        return False

    @property
    def path(self) -> Path:
        """Return the directory used for this function's saved call files."""
        function = inspect.unwrap(self.func)
        path = Path(inspect.getfile(function))
        path = path.parent / "resources_pytest_record_replay" / path.stem
        # If the function is a method, include the class name in the file path
        if inspect.ismethod(function):
            path = path / function.__self__.__class__.__name__
        path = path / function.__name__
        return path

    @property
    def files(self) -> List[Path]:
        """Return sorted pickle files in this function's recording directory."""
        return sorted(self.path.glob("*.pkl"))

    def _save(self, file: Path):
        """Create the recording directory and serialize calls to ``file``."""
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, "wb") as f:
            dill.dump(self.calls, f)

    def _load(self, file: Path):
        """Replace the in-memory call list with calls loaded from ``file``."""
        with open(file, "rb") as f:
            calls_data = dill.load(f)
            self.calls.clear()
            self.calls.extend(calls_data)

    def save(self, name: str):
        """Save calls in the default directory under ``name`` with a pickle suffix."""
        file = self.path / (name + ".pkl")
        self._save(file)


def has_funcwcalls(func: Callable) -> bool:
    """Return whether ``func`` has replay ``FunctionWCalls`` metadata."""
    return hasattr(func, "function_with_calls") and isinstance(
        func.function_with_calls,  # type: ignore
        FunctionWCalls,
    )


def get_funcwcalls(func: Callable) -> FunctionWCalls:
    """Return replay metadata attached to ``func``.

    Raises:
        ValueError: If ``func`` has no replay call metadata.
    """
    if not has_funcwcalls(func):
        raise ValueError("Function does not have calls.")
    return func.function_with_calls  # type: ignore


def set_funcwcalls(
    func: Callable[P, Optional[R]],
    record: bool,
    calls: Optional[List[Call]],
    file: Optional[Path],
) -> Callable[P, Optional[R]]:
    """Attach a ``FunctionWCalls`` wrapper while preserving function metadata."""
    function_with_calls = wraps(func)(
        FunctionWCalls(func, record=record, calls=calls, file=file)
    )

    @wraps(func)
    def patched_func(*args: P.args, **kwargs: P.kwargs):
        return function_with_calls(*args, **kwargs)

    patched_func.function_with_calls = function_with_calls  # type: ignore
    return patched_func
