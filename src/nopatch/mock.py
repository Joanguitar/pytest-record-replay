"""Callable recording and replay primitives."""

import importlib
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, AliasType, Hashable, List, Optional, Tuple
from unittest.mock import MagicMock, Mock, NonCallableMock, patch


@dataclass(frozen=True)
class _Call:
	function_name: str
	args: tuple
	kwargs: dict
	output: Any


RecordableCallable: AliasType = Callable[[Hashable, ...], Hashable]
_record_mode = False


def _resolve_target(target: str) -> Tuple[object, str, Callable]:
	if not isinstance(target, str) or "." not in target:
		raise TypeError("target must be a dotted module attribute path")

	parts = target.split(".")
	module = None
	module_parts = 0
	for end in range(len(parts) - 1, 0, -1):
		module_name = ".".join(parts[:end])
		try:
			module = importlib.import_module(module_name)
		except ModuleNotFoundError as error:
			if error.name != module_name and not module_name.startswith(f"{error.name}."):
				raise
			continue
		module_parts = end
		break

	if module is None:
		raise ModuleNotFoundError(f"could not import a module from target {target!r}")

	parent = module
	for part in parts[module_parts:-1]:
		parent = getattr(parent, part)
	attribute = parts[-1]
	function = getattr(parent, attribute)
	if not callable(function):
		raise TypeError(f"target {target!r} is not callable")
	return parent, attribute, function


def nopatch(target: str, calls: Optional[List[_Call]] = None) -> NoMockBase:
	"""Patch a callable, recording it under ``--record`` and replaying otherwise."""
	parent, attribute, function = _resolve_target(target)
	descriptor = inspect.getattr_static(parent, attribute)
	bind_instance = isinstance(parent, type) and not isinstance(
		descriptor, (staticmethod, classmethod)
	)
	if _record_mode:
		wrapper = NoMockRecord(
			function, calls=calls, name=target, bind_instance=bind_instance
		)
	else:
		position = _recall_positions.setdefault(target, [0])
		wrapper = NoMockRecall(
			function,
			recording=calls,
			name=target,
			position=position,
			bind_instance=bind_instance,
		)
	return patch.object(parent, attribute, new=wrapper)


Mock().side_effect

class NoMockBase(ABC, NonCallableMock):
	"""Abstract callable wrapper that does not let callers override outputs."""

	def __init__(
		self,
		function: Callable,
		name: Optional[str] = None,
		bind_instance: bool = False,
	):
		if not callable(function):
			raise TypeError("function must be callable")
		NonCallableMock.__init__(self, name=name)
		self._function = function
		self.__name__ = name or getattr(function, "__name__", type(function).__name__)
		self.name = name or self.__name__
		self.__doc__ = getattr(function, "__doc__", None)
		self._bind_instance = bind_instance

	@property
	def function(self) -> Callable:
		"""The function wrapped by this object."""
		return self._function

	def __get__(self, instance, owner=None):
		if instance is None or not self._bind_instance:
			return self
		return partial(self._call_with_instance, instance)

	def _call_with_instance(self, instance, *args, **kwargs):
		return self(instance, *args, **kwargs)

	@abstractmethod
	def __call__(self, *args, **kwargs):
		"""Invoke the wrapped behavior."""


class NoMockRecord(NoMockBase):
	"""Call a function normally while saving its inputs and output."""

	def __init__(
		self,
		function: RecordableCallable,
		calls: Optional[List[_Call]] = None,
		name: Optional[str] = None,
		bind_instance: bool = False,
	):
		super().__init__(function, name=name, bind_instance=bind_instance)
		self._calls = calls if calls is not None else []

	@property
	def records(self) -> Tuple[_Call, ...]:
		"""Recorded calls in invocation order."""
		return tuple(self._calls)

	def __call__(self, *args, **kwargs):
		output = self._function(*args, **kwargs)
		self._calls.append(_Call(self.name, args, dict(kwargs), output))
		return output

	def _call_with_instance(self, instance, *args, **kwargs):
		output = self._function(instance, *args, **kwargs)
		self._calls.append(_Call(self.name, args, dict(kwargs), output))
		return output


class NoMockRecall(NoMockBase):
	"""Replay the outputs recorded by a :class:`NoMockRecord` instance."""

	def __init__(
		self,
		function: RecordableCallable,
		recording: List[_Call],
		name: Optional[str] = None,
		position: Optional[List[int]] = None,
		bind_instance: bool = False,
	):
		super().__init__(function, name=name, bind_instance=bind_instance)
		self._calls = recording
		self._position = position if position is not None else [0]

	def __call__(self, *args, **kwargs):
		return self._recall(args, kwargs)

	def _call_with_instance(self, instance, *args, **kwargs):
		return self._recall(args, kwargs)

	def _recall(self, args, kwargs):
		position = self._position[0]
		if position >= len(self._calls):
			raise AssertionError("no recorded call remains to recall")

		expected = self._calls[position]
		if self.name != expected.function_name or args != expected.args or kwargs != expected.kwargs:
			raise AssertionError(
				"call does not match recording at position "
				f"{position}: expected args={expected.args!r}, "
				f"kwargs={expected.kwargs!r}; got args={args!r}, "
				f"kwargs={kwargs!r}"
			)

		self._position[0] += 1
		return expected.output

