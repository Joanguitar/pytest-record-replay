import unittest
from types import SimpleNamespace

import pytest

import nopatch.mock as mock_module
from nopatch.mock import FunctionWCalls, NoMockRecall, NoMockRecord, _Call


def identity(value=None):
    return value


def dependency(value):
    return f"result: {value}"


def test_record_and_recall_keyword_arguments():
    calls = []
    recorder = NoMockRecord("dependency", dependency, calls=calls)

    assert recorder(value="recorded") == "result: recorded"
    assert NoMockRecall("dependency", calls=calls)(value="recorded") == (
        "result: recorded"
    )


def test_recall_rejects_keyword_argument_mismatch():
    calls = []
    NoMockRecord("dependency", dependency, calls=calls)(value="expected")

    with pytest.raises(ValueError, match="Arguments mismatch"):
        NoMockRecall("dependency", calls=calls)(value="different")


def test_record_rejects_non_dillable_positional_argument():
    recorder = NoMockRecord("dependency", dependency)
    value = (item for item in ())

    with pytest.raises(ValueError, match="Argument .* is not picklable"):
        recorder(value)


def test_record_rejects_non_dillable_keyword_argument():
    recorder = NoMockRecord("dependency", dependency)
    value = (item for item in ())

    with pytest.raises(ValueError, match="Keyword argument value=.* is not picklable"):
        recorder(value=value)


def test_record_rejects_non_dillable_output():
    def returns_generator():
        return (item for item in ())

    recorder = NoMockRecord("dependency", returns_generator)

    with pytest.raises(ValueError, match="Output .* is not picklable"):
        recorder()


def test_function_wrapper_records_call(tmp_path, monkeypatch):
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    wrapper = FunctionWCalls(identity, record=True)

    assert wrapper("value") is None
    assert wrapper.record is True
    assert wrapper.calls == []
    assert len(wrapper.files) == 1


def test_function_wrapper_uses_provided_calls():
    calls = []

    wrapper = FunctionWCalls(identity, record=True, calls=calls)

    assert wrapper.calls is calls
    assert wrapper.record is True


def test_call_record_requires_empty_calls():
    wrapper = FunctionWCalls(identity, calls=[_Call("identity", (), {}, None)])

    with pytest.raises(AssertionError, match="Calls should be empty"):
        wrapper._call_record()


def test_call_record_saves_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    wrapper = FunctionWCalls(identity)

    wrapper._call_record("recorded")

    assert wrapper.calls == []
    assert len(wrapper.files) == 1


def test_call_recall_requires_recording_files(tmp_path, monkeypatch):
    wrapper = FunctionWCalls(identity)
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "missing"),
    )

    with pytest.raises(AssertionError, match="No recorded calls found"):
        wrapper._call_recall()


def test_call_recall_loads_files_and_resets_test_case(tmp_path, monkeypatch):
    events = []

    class Case(unittest.TestCase):
        def setUp(self):
            events.append("setUp")

        def tearDown(self):
            events.append("tearDown")

        def run_case(self):
            call = wrapper.calls[0]
            output = NoMockRecall(call.target, calls=wrapper.calls)()
            events.append((self._testMethodName, output))

    case = Case("run_case")
    wrapper = FunctionWCalls(case.run_case)
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    wrapper.calls.append(_Call("one", (), {}, "first"))
    wrapper.save("one")
    wrapper.calls[:] = [_Call("two", (), {}, "second")]
    wrapper.save("two")

    wrapper._call_recall()

    assert [event[1] for event in events if isinstance(event, tuple)] == [
        "first",
        "second",
    ]
    assert events[1:3] == ["tearDown", "setUp"]


def test_test_case_reset_skips_plain_function():
    FunctionWCalls(identity)._TestCaseReset()


def test_function_path_for_function_and_method():
    class Example:
        def method(self):
            return None

    function_path = FunctionWCalls(identity).path
    method_path = FunctionWCalls(Example().method).path

    assert function_path.name == "identity"
    assert method_path.parts[-2:] == ("Example", "method")


def test_pickle_files_are_sorted_and_save_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    wrapper = FunctionWCalls(identity)
    wrapper.calls.append(_Call("identity", ("value",), {}, "value"))
    wrapper.save("z-last")
    wrapper.save("a-first")

    assert [path.name for path in wrapper.files] == ["a-first.pkl", "z-last.pkl"]

    wrapper.calls.clear()
    wrapper._load_file(wrapper.files[0])
    assert wrapper.calls == [_Call("identity", ("value",), {}, "value")]


def test_pickle_preserves_python_value_types(tmp_path, monkeypatch):
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    wrapper = FunctionWCalls(identity)
    original = _Call("identity", (b"value",), {"tags": {"one", "two"}}, b"result")
    wrapper.calls.append(original)
    wrapper.save("typed-values")

    wrapper.calls.clear()
    wrapper._load_file(wrapper.files[0])

    assert wrapper.calls == [original]
    assert isinstance(wrapper.calls[0].args[0], bytes)
    assert isinstance(wrapper.calls[0].kwargs["tags"], set)


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


def test_nopatch_wraps_a_plain_function():
    decorated = mock_module.nopatch(f"{__name__}.dependency")(identity)

    assert isinstance(decorated, FunctionWCalls)
    assert decorated.record is False


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
        assert calls[0] == _Call(target, ("item",), {}, "result: item")
        assert len(decorated.files) == 1
    else:
        calls = [_Call(target, ("item",), {}, "recorded result")]
        wrapped = FunctionWCalls(function, record=False, calls=calls)
        wrapped.save("recorded")
        decorated = mock_module.nopatch(target)(wrapped)
        assert decorated("item") is None
        assert decorated.calls == []


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
    assert mock_module._record_mode is True


def test_pytest_recording_fixture_reads_option():
    plugin = __import__("nopatch.pytest_plugin", fromlist=["*"])
    request = SimpleNamespace(config=SimpleNamespace(getoption=lambda name: True))

    assert plugin.nopatch_recording.__wrapped__(request) is True
