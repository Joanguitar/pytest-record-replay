"""Callable recording and replay primitives."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Tuple, AliasType, Hashable
from unittest.mock import MagicMock, Mock, patch, NonCallableMock

@dataclass(frozen=True)
class _Call:
    function_name: str
	args: tuple
	kwargs: dict
	output: Any


RecordableCallable: AliasType = Callable[[Hashable, ...], Hashable]


class NoMockBase(ABC, NonCallableMock):
	"""Abstract callable wrapper that does not let callers override outputs."""

	def __init__(self, function: Callable, name: str | None = None):
		if not callable(function):
			raise TypeError("function must be callable")
		self._function = function
		self.__name__ = name or getattr(function, "__name__", type(function).__name__)
        self.name = name or self.__name__
		self.__doc__ = getattr(function, "__doc__", None)

	@property
	def function(self) -> Callable:
		"""The function wrapped by this object."""
		return self._function

	@abstractmethod
	def __call__(self, *args, **kwargs):
		"""Invoke the wrapped behavior."""


class NoMockRecord(NoMockBase):
	"""Call a function normally while saving its inputs and output."""

	def __init__(self, function: RecordableCallable, calls: None | list[_Call] = None, name: str | None = None):
		super().__init__(function, name=name)
		self._calls = calls if calls is not None else []

	@property
	def records(self) -> Tuple[_Call, ...]:
		"""Recorded calls in invocation order."""
		return tuple(self._calls)

	def __call__(self, *args, **kwargs):
		output = self._function(*args, **kwargs)
		self._calls.append(_Call(self.name, args, dict(kwargs), output))
		return output


class NoMockRecall(NoMockBase):
	"""Replay the outputs recorded by a :class:`NoMockRecord` instance."""

	def __init__(self, function: RecordableCallable, recording: list[_Call], name: str | None = None):
		super().__init__(function, name=name)
		self._calls = recording
		self._position = 0

	def __call__(self, *args, **kwargs):
		if self._position >= len(self._calls):
			raise AssertionError("no recorded call remains to recall")

		expected = self._calls[self._position]
		if self.name != expected.function_name or args != expected.args or kwargs != expected.kwargs:
			raise AssertionError(
				"call does not match recording at position "
				f"{self._position}: expected args={expected.args!r}, "
				f"kwargs={expected.kwargs!r}; got args={args!r}, "
				f"kwargs={kwargs!r}"
			)

		self._position += 1
		return expected.output

