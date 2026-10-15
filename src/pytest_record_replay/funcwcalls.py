"""Track test-function calls and persist or replay dependency histories."""

from __future__ import annotations

from functools import wraps
import inspect
from pathlib import Path
from typing import Any, Callable, Generic, List, Literal, Optional, Union, overload
import unittest
import warnings

import dill

from pytest_record_replay.typing import Call, P, R, P_, R_
from pytest_record_replay.util import record, recording, timestamp


class FunctionWCalls(Generic[P, R]):
    """Wrap a test function with recording, replay, and call-file management.

    In recording mode, the wrapped function runs and its patched calls are
    saved. In replay mode, saved calls are consumed while the function runs.
    Call data may be supplied directly, loaded from ``file``, or discovered
    from this function's default recordings directory.
    """

    __module__: str
    __name__: str
    __qualname__: str
    __doc__: Optional[str]
    __annotations__: dict
    __type_params__: tuple
    __wrapped__: Callable[P, R]

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
        record: Optional[bool] = ...,
        calls: Optional[List[Call]] = ...,
    ) -> FunctionWCalls[P, R]: ...

    @overload
    def __new__(
        cls,
        function: Callable[P, R],
        *,
        calls: List[Call],
        record: Optional[bool] = ...,
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

    @overload
    def __new__(
        cls,
        function: Callable[P, R],
        *,
        record: Optional[bool] = None,
        calls: Optional[List[Call]] = None,
        file: Optional[Path] = None,
    ) -> Union[FunctionWCalls[P, R], FunctionWCalls[P, R]]: ...

    def __new__(
        cls,
        function: Callable[P, Any],
        *,
        record: Optional[bool] = False,
        calls: Optional[List[Call]] = None,
        file: Optional[Path] = None,
    ) -> FunctionWCalls[P, Any]:
        return super().__new__(cls)

    def __init__(
        self,
        function: Callable,
        *,
        record: Optional[bool] = None,
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
        self._func = function
        self._record: Optional[bool] = record
        self.calls: List[Call] = calls if calls is not None else []
        if len(self.calls) > 0:
            if self.record:
                raise ValueError("Calls should be empty when recording.")
            if file is not None:
                warnings.warn("Both calls and file provided. Using calls.")
        self.file = file
        self._instance = None
        self._owner = None
        wraps(function)(self)

    def __get__(self, instance: Any, owner: Optional[type] = None):
        """Support instance-bound method access while preserving shared history."""
        self._instance = instance
        self._owner = owner
        return self

    @property
    def func(self) -> Callable[P, R]:
        if self.instance is not None:
            return self._func.__get__(self.instance, self._owner)
        return self._func

    @property
    def instance(self):
        return self._instance or getattr(self._func, "__self__", None)

    def decorated(
        self, decorator: Callable[[Callable[P, R]], Callable[P_, R_]]
    ) -> FunctionWCalls[P_, R_]:
        new_func = decorator(self._func)
        return FunctionWCalls(
            new_func, record=self.record, calls=self.calls, file=self.file
        )

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Invoke the wrapped function in the configured mode."""
        with record(self.record):
            if self.record:
                return self._call_record(*args, **kwargs)
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
        assert len(files) > 0, "No recordings found."
        for ii, file in enumerate(files):
            self._load(file)
            if ii > 0:
                self._TestCaseReset()
            self._call_recall_calls(*args, **kwargs)

    def _TestCaseReset(self) -> bool:
        """Reset a bound ``unittest.TestCase`` between recording files."""
        instance = self.instance
        if isinstance(instance, unittest.TestCase):
            instance.tearDown()
            instance.setUp()
            return True
        return False

    @property
    def record(self) -> bool:
        """Return the recording mode for this function."""
        return self._record if self._record is not None else recording()

    @property
    def path(self) -> Path:
        """Return the directory used for this function's saved call files."""
        function = inspect.unwrap(self._func)
        path = Path(inspect.getfile(function))
        path = path.parent / "resources_pytest_record_replay" / path.stem
        # If the function is a method, include the class name in the file path
        instance = self.instance
        if instance is not None:
            path = path / instance.__class__.__name__

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
