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
from pytest_record_replay.util import record, recording, set_calls, timestamp


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
            record: If true, save new calls; if false, replay saved calls. If
                ``None``, use the active recording mode when called.
            calls: Optional call history shared with patched dependency mocks.
                A nonempty history is replayed directly and cannot be used
                while recording.
            file: Optional pickle file used to save or load calls. When a
                nonempty ``calls`` list is provided, that list takes
                precedence and a warning is issued if ``file`` is also set.

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
        """Bind the wrapped function to an instance while preserving its history."""
        self._instance = instance
        self._owner = owner
        return self

    @property
    def func(self) -> Callable[P, R]:
        """Return the wrapped function, bound when accessed through an instance."""
        if self.instance is not None:
            return self._func.__get__(self.instance, self._owner)
        return self._func

    @property
    def func_r(self) -> Callable[P, R]:
        """Return self.func with record and set_calls contexts."""

        @wraps(self._func)
        def func_r(*args: P.args, **kwargs: P.kwargs) -> R:
            with record(self.record), set_calls(self.calls):
                return self.func(*args, **kwargs)

        return func_r

    @property
    def instance(self):
        """Return the bound instance, or the wrapped method's bound instance."""
        return self._instance or getattr(self._func, "__self__", None)

    def decorated(
        self, decorator: Callable[[Callable[P, R]], Callable[P_, R_]]
    ) -> FunctionWCalls[P_, R_]:
        """Return a decorated wrapper sharing this instance's settings and history."""
        new_func = decorator(self._func)
        return FunctionWCalls(
            new_func, record=self._record, calls=self.calls, file=self.file
        )

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Invoke the wrapped function in the configured mode."""
        if self.record:
            return self._call_record(*args, **kwargs)
        return self._call_recall(*args, **kwargs)

    def _call_record(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Run the function and save its dependency calls.

        Calls are saved to ``file`` when set, or to the default directory with
        the module-level timestamp otherwise.

        Raises:
            AssertionError: If the shared call history is not empty.
        """
        assert len(self.calls) == 0, "Calls should be empty before recording."
        with record(True):
            output = self.func_r(*args, **kwargs)
            if self.file is None:
                self.save(timestamp)
            else:
                self._save(self.file)
            return output

    def _call_recall(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Replay using the first available source of call history.

        A nonempty in-memory history takes precedence over ``file``; otherwise
        an explicit file takes precedence over files in the default directory.
        """
        if len(self.calls) > 0:
            return self._call_recall_calls(*args, **kwargs)
        if self.file is not None:
            return self._call_recall_file(*args, **kwargs)
        return self._call_recall_files(*args, **kwargs)

    def _call_recall_calls(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Run the function against in-memory calls and require full consumption."""
        output = self.func_r(*args, **kwargs)
        assert len(self.calls) == 0, (
            f"Unconsumed calls remain after replaying {self.calls}."
        )
        return output

    def _call_recall_file(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Load the configured file and replay its calls once."""
        assert self.file is not None
        self._load(self.file)
        return self._call_recall_calls(*args, **kwargs)

    def _call_recall_files(self, *args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore
        """Replay each saved call file in sorted order.

        A bound ``unittest.TestCase`` is torn down and set up between files.
        The wrapped function's return values are ignored.

        Raises:
            AssertionError: If no recording files are available.
        """
        files = self.files
        assert len(files) > 0, "No recordings found."
        for ii, file in enumerate(files):
            self._load(file)
            if ii > 0:
                self._TestCaseReset()
            self._call_recall_calls(*args, **kwargs)

    def _TestCaseReset(self) -> bool:
        """Reset a bound ``unittest.TestCase`` and report whether one was bound.

        A reset calls ``tearDown`` followed by ``setUp``. Returns ``False``
        when this wrapper is not bound to a ``unittest.TestCase`` instance.
        """
        instance = self.instance
        if isinstance(instance, unittest.TestCase):
            instance.tearDown()
            instance.setUp()
            return True
        return False

    @property
    def record(self) -> bool:
        """Return the explicit mode, or the active mode when none was set."""
        return self._record if self._record is not None else recording()

    @property
    def path(self) -> Path:
        """Return this function's default recordings directory.

        The path is based on the source module and function name, with a class
        name component when the wrapped function is bound to an instance.
        """
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
        """Return pickle recording files from the default directory, sorted by path."""
        return sorted(self.path.glob("*.pkl"))

    def _save(self, file: Path):
        """Create the parent directory and serialize the call history to ``file``."""
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, "wb") as f:
            dill.dump(self.calls, f)

    def _load(self, file: Path):
        """Load calls from ``file``, replacing the existing in-memory history."""
        with open(file, "rb") as f:
            calls_data = dill.load(f)
            self.calls.clear()
            self.calls.extend(calls_data)

    def save(self, name: str):
        """Save calls in the default directory as ``name`` with a ``.pkl`` suffix."""
        file = self.path / (name + ".pkl")
        self._save(file)


def ensure_functionwcalls(
    function: Union[Callable[P, R], FunctionWCalls[P, R], FunctionWCalls[P, None]],
) -> Union[FunctionWCalls[P, R], FunctionWCalls[P, None]]:
    if isinstance(function, FunctionWCalls):
        return function
    return FunctionWCalls(function)
