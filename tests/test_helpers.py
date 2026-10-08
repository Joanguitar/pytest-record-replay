from types import MappingProxyType

import pytest

from nopatch.funcwcalls import (
    FunctionWCalls,
    set_funcwcalls,
    get_funcwcalls,
    has_funcwcalls,
)
from nopatch.mock import (
    Call,
    _for_update,
    _update_argument,
)


def test_call_preserves_explicit_post_call_values():
    call = Call(
        "dependency",
        ("argument",),
        {"named": "value"},
        "result",
        post_args=("updated argument",),
        post_kwargs={"named": "updated value"},
    )

    assert call.post_args == ("updated argument",)
    assert call.post_kwargs == {"named": "updated value"}


def test_call_post_state_defaults_to_none_values_matching_arguments():
    call = Call(
        "identity",
        ("argument", 2),
        {"named": "value", "other": 3},
        "result",
    )

    assert call.post_args == (None, None)
    assert call.post_kwargs == {"named": None, "other": None}


def test_for_update_returns_none_for_unchanged_mutables():
    assert _for_update([1, 2], [1, 2]) is None
    assert _for_update({"a": [1]}, {"a": [1]}) is None


def test_for_update_returns_post_state_for_mutated_mutables():
    assert _for_update([1, 2], [2, 3]) == [2, 3]
    assert _for_update({"a": [1]}, {"a": [2]}) == {"a": [2]}
    assert _for_update(([1, 2], 1), ([2, 3], 1)) == ([2, 3], None)
    assert _for_update(
        MappingProxyType({"a": [1]}), MappingProxyType({"a": [2]})
    ) == MappingProxyType({"a": [2]})


def test_update_argument_updates_mutable_containers_in_place():
    for target, updated in [
        ([1, 2], [3, 4]),
        ({"a": [1]}, {"b": [2]}),
        ({1, 2}, {2, 3}),
        (bytearray(b"ab"), bytearray(b"cd")),
    ]:
        _update_argument(target, updated)
        assert target == updated


def test_for_update_handles_invalid_and_unhandled_mutables():
    with pytest.raises(TypeError, match="Cannot update mutable argument"):
        _for_update([1, 2], {"a": 1})

    with pytest.raises(ValueError, match="not picklable"):
        _for_update((item for item in ()), (item for item in ()))

    with pytest.raises(TypeError, match="Cannot update mutable argument"):
        _for_update("abc", "abd")


def test_update_argument_handles_none_and_nested_sequences():
    target = [1, 2]
    _update_argument(target, None)
    assert target == [1, 2]

    target = ([1, 2], {"a": [3]})
    updated = ([9], {"a": [4]})
    _update_argument(target, updated)
    assert target == updated

    with pytest.raises(TypeError, match="Cannot update mutable argument"):
        _update_argument([1, 2], {"a": 1})


def test_update_argument_updates_mutables_inside_read_only_mapping():
    target = MappingProxyType({"values": [1, 2]})
    updated = MappingProxyType({"values": [3, 4]})

    _update_argument(target, updated)

    assert target["values"] == [3, 4]


def test_update_argument_rejects_immutable_updates():
    with pytest.raises(TypeError, match="Cannot update mutable argument"):
        _update_argument(range(3), range(1, 4))


def test_funcwcalls_helpers_detect_and_return_wrapper_metadata():
    function = set_funcwcalls(lambda: None, record=False, calls=None, file=None)

    assert has_funcwcalls(function)
    assert isinstance(get_funcwcalls(function), FunctionWCalls)


def test_get_funcwcalls_rejects_unwrapped_callable():
    with pytest.raises(ValueError, match="does not have calls"):
        get_funcwcalls(lambda: None)
