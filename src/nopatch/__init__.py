"""Record/recall helpers for pytest."""

from importlib import import_module

__version__ = "0.1.0"

___imports = {
    ".mock": [
        "NoMockBase",
        "NoMockRecord",
        "NoMockRecall",
    ],
    ".util": ["recording"],
    ".decorators": ["nopatch", "nodecorator"],
    ".funcwcalls": ["has_funcwcalls", "get_funcwcalls"],
}

__all__ = [v for vs in ___imports.values() for v in vs]  # pyright: ignore[reportUnsupportedDunderAll]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    for key, value in ___imports.items():
        if name in value:
            return getattr(import_module(key, __name__), name)
