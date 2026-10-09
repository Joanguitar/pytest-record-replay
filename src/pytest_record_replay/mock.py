"""Callable recording and replay primitives."""

from abc import ABC, abstractmethod
from typing import (
    Callable,
    List,
    Optional,
)
from unittest.mock import Mock

import dill

from pytest_record_replay.typing import Call
from pytest_record_replay.util import _for_update, _update_argument


class MockRBase(ABC, Mock):
    """Base mock that shares a call list and supports method descriptor binding.

    Subclasses implement ``_execute_mock_call`` to either invoke and record the
    original callable or consume a matching saved call.
    """

    def __init__(
        self, target: str, *args, calls: Optional[List[Call]] = None, **kwargs
    ):
        """Initialize the mock and optionally share an existing call list."""
        super().__init__(*args, **kwargs)
        self._target = target
        self._calls = calls if calls is not None else []

    def __get__(self, instance, owner=None):
        """Bind a recorder to an instance method or return a replay descriptor."""
        if instance is None:
            return self
        if isinstance(self, MockRecord):
            function = self.function.__get__(instance, owner)
            return MockRecord(self._target, function, calls=self._calls)
        return MockReplay(self._target, calls=self._calls)

    @abstractmethod
    def _execute_mock_call(self, /, *args, **kwargs): ...


class MockRecord(MockRBase):
    """Invoke an original callable and append a serializable call record."""

    def __init__(
        self,
        target: str,
        function: Callable,
        *args,
        calls: Optional[List[Call]] = None,
        **kwargs,
    ):
        """Create a recorder for ``target`` using ``function`` as its original."""
        super().__init__(target, *args, calls=calls, **kwargs)
        self.function = function

    def _execute_mock_call(self, /, *args, **kwargs):
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


class MockReplay(MockRBase):
    """Replay saved outputs while validating inputs and restoring mutations."""

    def __init__(
        self, target: str, *args, calls: Optional[List[Call]] = None, **kwargs
    ):
        """Create a replay mock sharing the supplied call history."""
        super().__init__(target, *args, calls=calls, **kwargs)

    def _execute_mock_call(self, /, *args, **kwargs):
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
