from types import SimpleNamespace

import pytest

import nopatch.mock as mock_module
from nopatch.mock import FunctionWCalls


def identity(value=None):
    return value


def dependency(value):
    return f"result: {value}"


class MethodDependency:
    def value(self, item):
        return f"method: {item}"


def test_nodecorator_uses_global_and_explicit_modes(monkeypatch):
    monkeypatch.setattr(mock_module, "_record_mode", True)

    default_wrapper = mock_module.nodecorator()(identity)
    explicit_wrapper = mock_module.nodecorator(record=False)(identity)

    assert default_wrapper.record is True
    assert explicit_wrapper.record is False
    assert default_wrapper.__name__ == "identity"


def test_nodecorator_rejects_an_already_wrapped_function():
    wrapped = FunctionWCalls(identity)

    with pytest.raises(ValueError, match="should be applied before"):
        mock_module.nodecorator()(wrapped)


def test_nopatch_wraps_a_plain_function(monkeypatch):
    monkeypatch.setattr(mock_module, "_record_mode", False)
    decorated = mock_module.nopatch(f"{__name__}.dependency")(identity)

    assert callable(decorated)
    assert decorated.function_with_calls.func is not identity
    assert decorated.record is False


def test_nopatch_records_bound_method_without_receiver(tmp_path, monkeypatch):
    monkeypatch.setattr(mock_module, "_record_mode", True)
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    target = f"{__name__}.MethodDependency.value"
    instance = MethodDependency()

    @mock_module.nopatch(target)
    def call_method(item):
        return instance.value(item)

    assert call_method("item") is None
    assert call_method.calls[0].args == ("item",)
    assert call_method.calls[0].output == "method: item"


def test_mock_descriptor_supports_class_access_and_replay_binding():
    target = f"{__name__}.MethodDependency.value"
    calls = [
        mock_module._Call(
            target,
            ("item",),
            {},
            "replayed: item",
            post_args=(None,),
            post_kwargs={},
        )
    ]
    recall = mock_module.NoMockRecall(target, calls=calls)

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
    function = lambda value: dependency(value)

    if record:
        calls = []
        wrapped = FunctionWCalls(function, record=True, calls=calls)
        decorated = mock_module.nopatch(target)(wrapped)
        assert decorated("item") is None
        assert decorated.function_with_calls.files
        assert calls[0].target == target
        assert calls[0].args == ("item",)
        assert calls[0].kwargs == {}
        assert calls[0].output == "result: item"
        assert len(decorated.function_with_calls.files) == 1
    else:
        calls = [
            mock_module._Call(
                target,
                ("item",),
                {},
                "recorded result",
                post_args=(None,),
                post_kwargs={},
            )
        ]
        wrapped = FunctionWCalls(function, record=False, calls=calls)
        wrapped.save("recorded")
        decorated = mock_module.nopatch(target)(wrapped)
        assert decorated("item") is None
        assert decorated.calls == []
