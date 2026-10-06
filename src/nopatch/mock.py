"""Callable recording and replay primitives."""

import inspect
import unittest
from abc import ABC, abstractmethod
from collections.abc import MutableMapping, MutableSequence, MutableSet, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial, wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)
from unittest.mock import Mock, patch
import warnings

import dill
from typing_extensions import ParamSpec

from nopatch.typing import P, R, Call
from nopatch.util import _configure_patch, _for_update, _update_argument


class NoMockBase(ABC, Mock):
    """Base class for recording and replaying function calls."""

    def __init__(
        self, target: str, *args, calls: Optional[List[Call]] = None, **kwargs
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
        calls: Optional[List[Call]] = None,
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


class NoMockRecall(NoMockBase):
    """Replay the outputs recorded by a :class:`NoMockRecord` instance."""

    def __init__(
        self, target: str, *args, calls: Optional[List[Call]] = None, **kwargs
    ):
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

