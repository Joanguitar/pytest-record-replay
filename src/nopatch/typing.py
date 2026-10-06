
from dataclasses import dataclass, field
from typing import Any, Tuple

from typing_extensions import ParamSpec, TypeVar


P = ParamSpec("P")
R = TypeVar("R")



@dataclass(frozen=True)
class Call:
    target: str
    args: tuple
    kwargs: dict
    output: Any
    post_args: Tuple[Any, ...] = ()
    post_kwargs: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.post_args and self.args:
            object.__setattr__(self, "post_args", (None,) * len(self.args))
        if not self.post_kwargs and self.kwargs:
            object.__setattr__(self, "post_kwargs", dict.fromkeys(self.kwargs))