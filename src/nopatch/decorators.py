


from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Optional, Union, overload
from unittest.mock import patch

from nopatch.funcwcalls import FunctionWCalls, _set_patched_func, get_funcwcalls, has_funcwcalls
from nopatch.mock import NoMockBase, NoMockRecall, NoMockRecord
from nopatch.typing import P, R
from nopatch.util import recording


def nodecorator(
    record: Optional[bool] = None, file: Optional[Path] = None
) -> Callable[[Callable[P, R]], Callable[P, Optional[R]]]:
    """Return the function without any decoration."""
    if record is None:
        record = recording()

    def wrapper(
        func: Callable[P, R],
    ) -> Callable[P, Optional[R]]:
        if has_funcwcalls(func):
            raise AttributeError(
                "@nodecorator should be applied before any @nopatch decorator."
            )
        _func = patch(f"nopatch.util.recording", lambda: record)(func)
        return _set_patched_func(_func, record=record, calls=None, file=file)

    return wrapper


def nopatchermock(target: str, funcwcalls: FunctionWCalls) -> NoMockBase:
    record = funcwcalls.record
    calls = funcwcalls.calls
    if record:
        patched_func, _ = patch(target).get_original()
        return NoMockRecord(target, patched_func, calls=calls)
    return NoMockRecall(target, calls=calls)


@overload
def nopatcher(
    func: FunctionWCalls[P, R], target: str
) -> FunctionWCalls[P, R]: ...
@overload
def nopatcher(
    func: Callable[P, Optional[R]], target: str
) -> Callable[P, Optional[R]]: ...


def nopatcher(
    func: Union[Callable[P, Optional[R]], FunctionWCalls[P, R]],
    target: str,
) -> Union[Callable[P, Optional[R]], FunctionWCalls[P, R]]:
    return_functionWCalls = isinstance(func, FunctionWCalls)
    if return_functionWCalls:
        function_with_calls: FunctionWCalls = func
    else:
        if not has_funcwcalls(func):
            func = nodecorator()(func)
        function_with_calls = get_funcwcalls(func)
    func = function_with_calls.func
    record = function_with_calls.record
    calls = function_with_calls.calls
    file = function_with_calls.file
    mock = nopatchermock(target, function_with_calls)
    _func = patch(target, mock)(func)
    if return_functionWCalls:
        return FunctionWCalls(_func, record=record, calls=calls, file=file)
    else:
        return _set_patched_func(_func, record=record, calls=calls, file=file)


def nopatch(target: str):
    return partial(nopatcher, target=target)