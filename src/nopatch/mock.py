"""Callable recording and replay primitives."""

import importlib
import inspect
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, AliasType, Hashable, List, Optional, Tuple
from unittest.mock import MagicMock, Mock, NonCallableMock, patch


@dataclass(frozen=True)
class _Call:
	target: str
	args: tuple
	kwargs: dict
	output: Any


RecordableCallable: AliasType = Callable[[Hashable, ...], Hashable]
_record_mode = False


class NoMockBase(ABS, Mock):
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
		**kwargs
	):
		super().__init__(*args, **kwargs)
		self._calls = calls if calls is not None else []

	def _execute_mock_call(self, /, *args, **kwargs):
		output = self._target(*args, **kwargs)
		self._calls.append(_Call(
			target=self._target,
			args=args,
			kwargs=kwargs,
			output=output
		))
		return output


class NoMockRecall(NoMockBase):
	"""Replay the outputs recorded by a :class:`NoMockRecord` instance."""

	def __init__(
		self,
		target: str,
		*args,
		calls: List[_Call] = None,
		**kwargs
	):
		super().__init__(*args, **kwargs)
		self._calls = calls if calls is not None else []

	def _execute_mock_call(self, /, *args, **kwargs):
		call = self._calls.pop(0)
		if call.target != self._target:
			raise ValueError(f"Target mismatch: expected {call.target}, got {self._target}")
		if call.args != args or call.kwargs != kwargs:
			raise ValueError(f"Arguments mismatch: expected {call.args} and {call.kwargs}, got {args} and {kwargs}")
		return call.output



class FunctionWCalls:
	"""Wrap a function to have calls attribute."""

	def __init__(self, function: Callable, recording: bool = False):
		self._function = function
		self.calls: List[_Call] = []
		self.recording: bool = recording

	def __call__(self, *args, **kwargs):
		return self._function(*args, **kwargs)

	def file(self) -> Path:
		"""Return a file unique to the function."""
		file = Path(inspect.getfile(self._function))
		file = file.parent / file.stem
		# If the function is a method, include the class name in the file path
		if inspect.ismethod(self._function):
			file = file / self._function.__self__.__class__.__name__
		file = file / self._function.__name__
		return file.with_suffix(".json")



def nodecorator(recording: bool = False) -> Callable:
	"""Return the function without any decoration."""
	def wrapper(func: Callable) -> FunctionWCalls:
		return wraps(func)(FunctionWCalls(func, recording=recording))
	return wrapper


def nopatch(target: str):
	def wrapper(func: FunctionWCalls) -> FunctionWCalls:
		calls = func.calls
		if func.recording:
			patched_func, _ = patch(target).get_original()
			return patch(target, NoMockRecord(target, patched_func, calls=calls))(func)
		else:
			return patch(target, NoMockRecall(target, calls=calls))(func)