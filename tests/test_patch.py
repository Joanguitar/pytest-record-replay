import pytest

from nopatch.decorators import nodecorator, nopatch
from nopatch.mock import NoMockRecall
import nopatch.util as util_module
from nopatch.typing import Call
from nopatch.util import recording
from nopatch.funcwcalls import FunctionWCalls, get_funcwcalls


def identity(value=None) -> None:
    return None


def dependency(value):
    return f"result: {value}"


def try_raise(error: Exception) -> None:
    if isinstance(error, Exception):
        raise error


class MethodDependency:
    def value(self, item):
        return f"method: {item}"


def test_nodecorator_uses_global_and_explicit_modes(monkeypatch):
    monkeypatch.setattr(util_module, "_recording", True)

    default_wrapper = nodecorator()(try_raise)
    explicit_wrapper = nodecorator(record=False)(try_raise)

    assert get_funcwcalls(default_wrapper).record is True
    assert get_funcwcalls(explicit_wrapper).record is False
    assert default_wrapper.__name__ == "try_raise"


def test_nodecorator_patches_module_recording_reference_only(monkeypatch):
    monkeypatch.setattr(util_module, "_recording", False)
    observed_recording = []

    def observe_recording() -> None:
        observed_recording.append((recording(), util_module.recording()))

    wrapper = nodecorator(record=True)(observe_recording)

    assert get_funcwcalls(wrapper).func() is None
    assert observed_recording == [(False, True)]
    assert recording() is False
    assert util_module.recording() is False


def test_nodecorator_rejects_an_already_wrapped_function():
    wrapped = nodecorator()(identity)

    with pytest.raises(AttributeError, match="should be applied before"):
        nodecorator()(wrapped)


def test_nopatch_wraps_a_plain_function(monkeypatch):
    monkeypatch.setattr(util_module, "_recording", False)
    decorated = nopatch(f"{__name__}.dependency")(identity)

    assert callable(decorated)
    funcwcalls = get_funcwcalls(decorated)
    assert funcwcalls.func is not identity
    assert funcwcalls.record is False


def test_nopatch_records_bound_method_without_receiver(tmp_path, monkeypatch):
    monkeypatch.setattr(util_module, "_recording", True)
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    target = f"{__name__}.MethodDependency.value"
    instance = MethodDependency()

    @nopatch(target)
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
    recall = NoMockRecall(target, calls=calls)

    assert recall.__get__(None, MethodDependency) is recall
    bound_recall = recall.__get__(MethodDependency(), MethodDependency)
    assert bound_recall("item") == "replayed: item"


@pytest.mark.parametrize("record", [False, True])
def test_nopatch_handles_existing_wrapper_and_both_modes(record, tmp_path, monkeypatch):
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    target = f"{__name__}.dependency"

    def function(value) -> None:
        dependency(value)

    wrapped = nodecorator(record=record)(function)
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
        funcwcalls.save("recorded")

    decorated = nopatch(target)(wrapped)
    funcwcalls = get_funcwcalls(decorated)
    assert decorated("item") is None

    if record:
        assert funcwcalls.files
        assert calls[0].target == target
        assert calls[0].args == ("item",)
        assert calls[0].kwargs == {}
        assert calls[0].output == "result: item"
        assert len(funcwcalls.files) == 1
    else:
        assert funcwcalls.calls == []
