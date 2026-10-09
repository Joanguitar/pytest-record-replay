"""Record and replay dependency calls in pytest tests.

The public classes and helpers are imported lazily to keep package import
lightweight. They are available directly from :mod:`pytest_record_replay`.
"""

from importlib import import_module

__version__ = "0.1.0"

___imports = {
    ".util": ["recording"],
    ".decorators": ["patch_replay", "set_replay", "patcher_replay"],
}

__all__ = [v for vs in ___imports.values() for v in vs]  # pyright: ignore[reportUnsupportedDunderAll]


def __getattr__(name):
    """Load a public API symbol from the module that defines it.

    Raises:
        AttributeError: If ``name`` is not part of the public API.
    """
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    for key, value in ___imports.items():
        if name in value:
            return getattr(import_module(key, __name__), name)
