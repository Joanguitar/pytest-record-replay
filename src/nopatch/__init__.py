"""Record/recall helpers for pytest."""

from importlib import import_module

__version__ = "0.0.1"

__all__ = [
    "NoMockBase",
    "NoMockRecord",
    "NoMockRecall",
    "nopatch",
    "nodecorator",
    "recording",
]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(".mock", __name__), name)
