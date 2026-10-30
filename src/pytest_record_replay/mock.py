"""Callable recording and replay primitives."""

from typing import (
    Any,
    Callable,
    List,
    Optional,
)
from unittest.mock import Mock, patch

import dill

from pytest_record_replay.typing import Call
from pytest_record_replay import util
from pytest_record_replay.util import (
    _for_update,
    _update_argument,
    get_calls,
)


class MockR(Mock):
    """Mock that records calls to, or replays calls for, a target callable.

    The call history can be shared with a :class:`FunctionWCalls` wrapper.
    Instances also act as descriptors so patched methods can be bound to their
    original receivers.
    """

    def __init__(
        self,
        target: str,
        *args,
        function: Optional[Callable] = None,
        calls: Optional[List[Call]] = None,
        **kwargs,
    ):
        """Initialize the mock and optionally share an existing call list.

        The target identifies the callable to patch. Alternatively, the
        original callable may be supplied as the first positional argument
        after ``target``. Remaining positional and keyword arguments are
        passed to :class:`unittest.mock.Mock`.
        """
        super().__init__(*args, **kwargs)
        self._target = target
        self._calls: Optional[List[Call]] = calls
        self._instance: Optional[Any] = None
        self._owner: Optional[type] = None
        self._function: Callable
        if function is None:
            self._function, _ = patch(self._target).get_original()
        else:
            self._function = function

    @property
    def function(self):
        """Return the original callable, bound when accessed through an instance."""
        if self._instance is not None:
            return self._function.__get__(self._instance, self._owner)
        return self._function

    @property
    def calls(self) -> List[Call]:
        """Return the shared call history, or an empty list if none exists."""
        return get_calls() if self._calls is None else self._calls

    def __get__(self, instance, owner=None):
        """Bind the original method to ``instance`` and return this mock."""
        self._instance = instance
        self._owner = owner
        return self

    def __call__(self, *args, **kwargs):
        if util.recording() and util.recording_disabled():
            # Bypass Mock
            return self.function(*args, **kwargs)
        return super().__call__(*args, **kwargs)

    def _execute_mock_call(self, /, *args, **kwargs):
        """Dispatch the call according to the active recording mode."""
        if util.recording():
            return self._execute_mock_call_record(*args, **kwargs)
        return self._execute_mock_call_replay(*args, **kwargs)

    def _execute_mock_call_record(self, /, *args, **kwargs):
        """Validate and snapshot a call, invoke its original, then record it.

        Raises:
            ValueError: If an argument or the callable's output cannot be
                serialized with dill.
        """
        # Make sure that the arguments and the output are picklable before recording
        for arg in args:
            if not dill.pickles(arg, exact=True):
                raise ValueError(f"Argument {arg} is not picklable.")
        for key, value in kwargs.items():
            if not dill.pickles(value, exact=True):
                raise ValueError(f"Keyword argument {key}={value} is not picklable.")
        recorded_args = dill.copy(args)
        recorded_kwargs = dill.copy(kwargs)
        with util.disable_recording():  # Force next calls to skip mocking
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
        self.calls.append(
            Call(
                target=self._target,
                args=recorded_args,
                kwargs=recorded_kwargs,
                output=recorded_output,
                post_args=post_args,
                post_kwargs=post_kwargs,
            )
        )
        return output

    def _execute_mock_call_replay(self, /, *args, **kwargs):
        """Consume a saved call, validate it, apply argument updates, and return its output.

        Raises:
            IndexError: If no saved call remains.
            ValueError: If the saved target or arguments do not match this call.
            TypeError: If a saved argument update cannot be applied.
        """
        call = self.calls.pop(0)
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
