from collections import defaultdict, deque
from types import SimpleNamespace

import pytest

import nopatch
import nopatch.mock as mock_module
from nopatch.mock import (
    _Call,
    _can_update,
    _configure_patch,
    _for_update,
    _update_argument,
)


def test_call_post_state_defaults_to_none_values_matching_arguments():
    call = _Call(
        "identity",
        ("argument", 2),
        {"named": "value", "other": 3},
        "result",
    )

    assert call.post_args == (None, None)
    assert call.post_kwargs == {"named": None, "other": None}


def test_can_update_detects_mutable_collections():
    assert _can_update([1, 2])
    assert _can_update({"items": [1, 2]})
    assert _can_update({1, 2})
    assert not _can_update((1, 2))
    assert not _can_update("abc")


def test_for_update_returns_none_for_unchanged_mutables():
    assert _for_update([1, 2], [1, 2]) is None
    assert _for_update({"a": [1]}, {"a": [1]}) is None


def test_for_update_returns_post_state_for_mutated_mutables():
    assert _for_update([1, 2], [2, 3]) == [2, 3]
    assert _for_update({"a": [1]}, {"a": [2]}) == {"a": [2]}


def test_update_argument_handles_additional_mutable_collections():
    target = {
        "values": [1, 2],
        "mapping": defaultdict(list, {"a": [1]}),
        "set": {1, 2},
        "bytes": bytearray(b"ab"),
        "queue": deque([1, 2]),
        "nested": ([1], {"k": [2]}, bytearray(b"x")),
    }
    updated = {
        "values": [3, 4],
        "mapping": defaultdict(list, {"b": [5]}),
        "set": {3, 4},
        "bytes": bytearray(b"cd"),
        "queue": deque([3, 4]),
        "nested": ([5], {"k": [6]}, bytearray(b"y")),
    }

    for key, value in updated.items():
        _update_argument(target[key], value)

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


def test_update_argument_rejects_wrong_type():
    with pytest.raises(TypeError, match="Cannot update mutable argument"):
        _update_argument("abc", "abd")

    with pytest.raises(TypeError, match="Cannot update mutable argument"):
        _update_argument(range(3), range(1, 4))


def test_configure_patch_updates_global_record_mode():
    _configure_patch(False)
    assert mock_module._recording is False

    _configure_patch(True)
    assert mock_module._recording is True


def test_package_attribute_lookup_reports_missing_names():
    assert nopatch.__all__ == [
        "NoMockBase",
        "NoMockRecord",
        "NoMockRecall",
        "nopatch",
        "nodecorator",
        "recording",
    ]
    assert nopatch.__getattr__("NoMockRecord") is mock_module.NoMockRecord
    with pytest.raises(AttributeError, match="has no attribute"):
        nopatch.__getattr__("missing")


def test_pytest_plugin_hooks_configure_record_mode():
    options = []
    mock_module._configure_patch(False)

    class Parser:
        def addoption(self, *args, **kwargs):
            options.append((args, kwargs))

    mock_module_plugin = __import__("nopatch.pytest_plugin", fromlist=["*"])
    mock_module_plugin.pytest_addoption(Parser())
    mock_module_plugin.pytest_configure(
        SimpleNamespace(getoption=lambda name: name == "--record")
    )

    assert options[0][0] == ("--record",)
    assert options[0][1]["action"] == "store_true"
    assert mock_module._recording is True


def test_pytest_recording_fixture_reads_option():
    plugin = __import__("nopatch.pytest_plugin", fromlist=["*"])
    request = SimpleNamespace(config=SimpleNamespace(getoption=lambda name: True))

    assert plugin.nopatch_recording.__wrapped__(request) is True
