"""Callable recording and replay primitives."""

from abc import ABC
from typing import (
    Any,
    List,
    Optional,
)
from unittest.mock import Mock, patch

import dill

from pytest_record_replay.typing import Call
from pytest_record_replay import util
from pytest_record_replay.util import _for_update, _update_argument


class MockR(ABC, Mock):
    """Base mock that shares a call list and supports method descriptor binding.

    Subclasses implement ``_execute_mock_call`` to either invoke and record the
    original callable or consume a matching saved call.
    """

    def __init__(
        self, target: str, *args, calls: Optional[List[Call]] = None, **kwargs
    ):
        """Initialize the mock and optionally share an existing call list."""
        user_function = args[0] if args and callable(args[0]) else None
        if user_function is not None:
            args = args[1:]
        super().__init__(*args, **kwargs)
        self._target = target
        self._calls = calls if calls is not None else []
        self._instance: Optional[Any] = None
        self._owner: Optional[type] = None
        function = user_function
        if function is None:
            function, _ = patch(self._target).get_original()
        self._function = function

    @property
    def function(self):
        """The callable being recorded or replayed."""
        if self._instance is not None:
            return self._function.__get__(self._instance, self._owner)
        return self._function

    def __get__(self, instance, owner=None):
        """Bind a recorder to an instance method or return a replay descriptor."""
        self._instance = instance
        self._owner = owner
        return self

    def _execute_mock_call(self, /, *args, **kwargs):
        if util.recording():
            return self._execute_mock_call_record(*args, **kwargs)
        return self._execute_mock_call_replay(*args, **kwargs)

    def _execute_mock_call_record(self, /, *args, **kwargs):
        """Validate, deep-copy, invoke, and record one call."""
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
        """Consume and validate the next call, apply updates, and return output."""
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
