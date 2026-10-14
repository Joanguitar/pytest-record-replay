"""Shared type variables and the recorded-call data structure."""

from dataclasses import dataclass, field
from typing import Any, Tuple

from typing_extensions import ParamSpec, TypeVar


P = ParamSpec("P")
R = TypeVar("R")
P_ = ParamSpec("P_")
R_ = TypeVar("R_")

T = TypeVar("T", bound=type)


@dataclass()
class Call:
    """One invocation of a patched callable and its captured post-call state.

    ``post_args`` and ``post_kwargs`` contain mutations that should be applied
    to mutable arguments during replay. Missing post-call values default to
    ``None`` for each corresponding argument, meaning no update is needed.
    """

    target: str
    """Fully qualified name of the patched callable."""
    args: tuple
    """Positional arguments supplied to the callable."""
    kwargs: dict
    """Keyword arguments supplied to the callable."""
    output: Any
    """Value returned by the callable."""
    post_args: Tuple[Any, ...] = ()
    """Post-call updates corresponding to ``args``."""
    post_kwargs: dict = field(default_factory=dict)
    """Post-call updates corresponding to ``kwargs``."""

    def __post_init__(self):
        """Fill omitted post-call state with no-update markers."""
        if not self.post_args and self.args:
            object.__setattr__(self, "post_args", (None,) * len(self.args))
        if not self.post_kwargs and self.kwargs:
            object.__setattr__(self, "post_kwargs", dict.fromkeys(self.kwargs))
