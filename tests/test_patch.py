from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pytest_record_replay.mock import MockReplay
from pytest_record_replay.decorators import patcher_replay, patch_replay, set_replay
import pytest_record_replay.util as util_module
from pytest_record_replay.typing import Call
from pytest_record_replay.funcwcalls import FunctionWCalls, get_funcwcalls


def identity(value=None) -> None:
    return value


def dependency(value):
    return f"result: {value}"


def try_raise(error: Exception) -> None:
    if isinstance(error, Exception):
        raise error


class MethodDependency:
    def value(self, item):
        return f"method: {item}"


def test_set_replay_uses_global_and_explicit_modes(monkeypatch):
    monkeypatch.setattr(util_module, "_recording", True)

    default_wrapper = set_replay()(try_raise)
    explicit_wrapper = set_replay(record=False)(try_raise)

    assert get_funcwcalls(default_wrapper).record is True
    assert get_funcwcalls(explicit_wrapper).record is False
    assert default_wrapper.__name__ == "try_raise"


def test_set_replay_rejects_an_already_wrapped_function():
    wrapped = set_replay()(identity)

    with pytest.raises(AttributeError, match="should be applied before"):
        set_replay()(wrapped)


@pytest.mark.parametrize("record", [True, False])
@pytest.mark.parametrize("file", [None, Path("path/to/file.pkl")])
def test_replay_patch_preserves_existing_functionwcalls_metadata(
    record: bool, file: Path
):
    target = f"{__name__}.dependency"
    wrapped = set_replay(record=record, file=file)(dependency)
    function_with_calls = get_funcwcalls(wrapped)

    patched = patcher_replay(function_with_calls, target)

    assert isinstance(patched, FunctionWCalls)
    assert patched.record == record
    assert patched.calls == function_with_calls.calls
    assert patched.file == function_with_calls.file
    assert callable(patched.func)


@patch("pytest_record_replay.funcwcalls.FunctionWCalls._save", new=Mock())
def test_replay_records_bound_method_without_receiver(monkeypatch):
    monkeypatch.setattr(util_module, "_recording", True)
    target = f"{__name__}.MethodDependency.value"
    instance = MethodDependency()

    @patch_replay(target)
    def call_method(item) -> None:
        instance.value(item)

    assert call_method("item") is None
    calls = get_funcwcalls(call_method).calls
    assert calls[0].args == ("item",)
    assert calls[0].output == "method: item"


def test_mock_descriptor_supports_class_access_and_replay_binding():
    target = f"{__name__}.MethodDependency.value"
    calls = [
        Call(
            target,
            ("item",),
            {},
            "replayed: item",
            post_args=(None,),
            post_kwargs={},
        )
    ]
    recall = MockReplay(target, calls=calls)

    assert recall.__get__(None, MethodDependency) is recall
    bound_recall = recall.__get__(MethodDependency(), MethodDependency)
    assert bound_recall("item") == "replayed: item"


@pytest.mark.parametrize("record", [False, True])
@patch("pytest_record_replay.funcwcalls.FunctionWCalls._save", new=Mock())
def test_replay_handles_existing_wrapper_and_both_modes(record):
    target = f"{__name__}.dependency"

    def function(value) -> None:
        dependency(value)

    wrapped = set_replay(record=record)(function)
    funcwcalls = get_funcwcalls(wrapped)
    calls = funcwcalls.calls

    if not record:
        calls.append(
            Call(
                target,
                ("item",),
                {},
                "recorded result",
                post_args=(None,),
                post_kwargs={},
            )
        )
    decorated = patch_replay(target)(wrapped)
    funcwcalls = get_funcwcalls(decorated)
    assert decorated("item") is None

    if record:
        assert calls[0].target == target
        assert calls[0].args == ("item",)
        assert calls[0].kwargs == {}
        assert calls[0].output == "result: item"
    else:
        assert funcwcalls.calls == []
