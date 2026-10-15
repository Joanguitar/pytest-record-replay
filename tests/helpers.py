from contextlib import contextmanager
from contextvars import ContextVar

from functools import wraps
from typing import Dict, Set, Optional, Generator


run_count: ContextVar[Optional[Dict[str, int]]] = ContextVar(
    "pytest_record_replay_recording", default=None
)
bumping_funcs: Set[str] = set()


@contextmanager
def counting() -> Generator[Dict[str, int], None, None]:
    count = {key: 0 for key in ["identity", "dependency", "multiply", "describe"]}
    tocken = run_count.set(count)
    try:
        yield count
    finally:
        run_count.reset(tocken)


def bump_count(key: str) -> None:
    count = run_count.get()
    if count is not None:
        count[key] += 1


def bumping(func):
    bumping_funcs.add(func.__name__)

    @wraps(func)
    def wrapper(*args, **kwargs):
        bump_count(func.__name__)
        return func(*args, **kwargs)

    return wrapper


@bumping
def identity(value=None):
    return value


@bumping
def dependency(value):
    return f"result: {value}"


@bumping
def multiply(value):
    return value * 2


@bumping
def describe(name):
    return {"name": name, "active": True}


@bumping
def try_raise(error: Exception) -> None:
    if isinstance(error, Exception):
        raise error


class MethodDependency:
    @bumping
    def value(self, item):
        return f"method: {item}"
