import unittest

import nopatch.mock as mock_module
from nopatch.mock import FunctionWCalls, NoMockRecall, NoMockRecord, _Call


def test_timestamp_is_safe_for_windows_paths():
    assert not any(char in mock_module.timestamp for char in '<>:"/\\|?*')


def identity(value=None):
    return value


def dependency(value):
    return f"result: {value}"


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

    try:
        wrapper._call_record()
    except AssertionError as exc:
        assert "Calls should be empty" in str(exc)
    else:
        raise AssertionError("Expected AssertionError from _call_record")


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

    try:
        wrapper._call_recall()
    except AssertionError as exc:
        assert "No recorded calls found" in str(exc)
    else:
        raise AssertionError("Expected AssertionError from _call_recall")


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
    wrapper.calls.append(_Call("one", (), {}, "first", post_args=(), post_kwargs={}))
    wrapper.save("one")
    wrapper.calls[:] = [_Call("two", (), {}, "second", post_args=(), post_kwargs={})]
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
    wrapper.calls.append(
        _Call("identity", ("value",), {}, "value", post_args=(None,), post_kwargs={})
    )
    wrapper.save("z-last")
    wrapper.save("a-first")

    assert [path.name for path in wrapper.files] == ["a-first.pkl", "z-last.pkl"]

    wrapper.calls.clear()
    wrapper._load_file(wrapper.files[0])
    assert wrapper.calls == [
        _Call("identity", ("value",), {}, "value", post_args=(None,), post_kwargs={})
    ]


def test_pickle_preserves_python_value_types(tmp_path, monkeypatch):
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    wrapper = FunctionWCalls(identity)
    original = _Call(
        "identity",
        (b"value",),
        {"tags": {"one", "two"}},
        b"result",
        post_args=(None,),
        post_kwargs={"tags": None},
    )
    wrapper.calls.append(original)
    wrapper.save("typed-values")

    wrapper.calls.clear()
    wrapper._load_file(wrapper.files[0])

    assert wrapper.calls == [original]
    assert isinstance(wrapper.calls[0].args[0], bytes)
    assert isinstance(wrapper.calls[0].kwargs["tags"], set)
