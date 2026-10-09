from contextlib import contextmanager
import unittest
from unittest.mock import Mock, PropertyMock, patch

import pytest

from pytest_record_replay.util import timestamp
from pytest_record_replay.mock import (
    MockReplay,
    Call,
)
from pytest_record_replay.funcwcalls import FunctionWCalls
from pytest_record_replay.decorators import replay_mock


def test_timestamp_is_safe_for_windows_paths():
    assert not any(char in timestamp for char in '<>:"/\\|?*')


def identity(value=None):
    return value


def dependency(value):
    return f"result: {value}"


def call_funcs(value):
    identity_output = identity(value)
    dependency_output = dependency(value)
    if identity_output != value or dependency_output != f"result: {value}":
        raise ValueError
    return value


def identity_calls(value):
    return [Call(f"{__name__}.identity", (value,), {}, value)]


def dependency_calls(value):
    return [Call(f"{__name__}.dependency", (value,), {}, f"result: {value}")]


def call_funcs_calls(value):
    return identity_calls(value) + dependency_calls(value)


def patch_identity(funcwcalls: FunctionWCalls):
    return patch(
        f"{__name__}.identity", replay_mock(f"{__name__}.identity", funcwcalls)
    )


def patch_dependency(funcwcalls: FunctionWCalls):
    return patch(
        f"{__name__}.dependency", replay_mock(f"{__name__}.dependency", funcwcalls)
    )


@contextmanager
def patch_both(funcwcalls: FunctionWCalls):
    with patch_identity(funcwcalls), patch_dependency(funcwcalls):
        yield


@pytest.mark.parametrize(
    "value", ["value", None, 0, 3.14, [1, 2], {"a": 1, "b": 2}, (1, 2)]
)
@patch("pytest_record_replay.funcwcalls.FunctionWCalls._save", new=Mock())
def test_function_wrapper_records_call(value):
    funcwcalls = FunctionWCalls(call_funcs, record=True)

    with patch_identity(funcwcalls):
        assert funcwcalls(value) == value
        assert funcwcalls.record is True
        assert funcwcalls.calls == identity_calls(value)


@pytest.mark.parametrize(
    "value", ["value", None, 0, 3.14, [1, 2], {"a": 1, "b": 2}, (1, 2)]
)
@patch("pytest_record_replay.funcwcalls.FunctionWCalls._save", new=Mock())
def test_function_wrapper_records_calls(value):
    funcwcalls = FunctionWCalls(call_funcs, record=True)

    with patch_both(funcwcalls):
        assert funcwcalls(value) == value
        assert funcwcalls.record is True
        assert funcwcalls.calls == call_funcs_calls(value)


def test_function_wrapper_uses_provided_calls():
    calls = []

    funcwcalls = FunctionWCalls(identity, record=True, calls=calls)

    assert funcwcalls.calls is calls
    assert funcwcalls.record is True


def test_function_wrapper_rejects_calls_when_recording():
    calls = [Call("identity", (), {}, None)]

    with pytest.raises(ValueError, match="Calls should be empty"):
        FunctionWCalls(identity, record=True, calls=calls)


def test_function_wrapper_warns_when_calls_and_file_are_provided(tmp_path):
    calls = [Call("identity", (), {}, None)]

    with pytest.warns(UserWarning, match="Both calls and file provided"):
        funcwcalls = FunctionWCalls(identity, calls=calls, file=tmp_path / "calls.pkl")

    assert funcwcalls.calls is calls


def test_recall_rejects_unconsumed_in_memory_calls():
    calls = [Call("identity", (), {}, "unused")]
    funcwcalls = FunctionWCalls(lambda: None, calls=calls)

    with pytest.raises(AssertionError, match="Unconsumed calls remain"):
        funcwcalls()


@pytest.mark.parametrize(
    "value", ["value", None, 0, 3.14, [1, 2], {"a": 1, "b": 2}, (1, 2)]
)
def test_function_wrapper_records_and_recalls_from_explicit_file(tmp_path, value):
    file = tmp_path / "recordings" / "explicit.pkl"
    recorder = FunctionWCalls(
        call_funcs,
        record=True,
        file=file,
    )

    with patch_both(recorder):
        assert recorder(value) == value
        assert file.is_file()
        assert recorder.calls == call_funcs_calls(value)

    replayer = FunctionWCalls(
        call_funcs,
        record=False,
        file=file,
    )

    with patch_both(replayer):
        assert replayer(value) == value
        assert replayer.calls == []


def test_call_record_requires_empty_calls():
    funcwcalls = FunctionWCalls(identity, calls=[Call("identity", (), {}, None)])

    with pytest.raises(AssertionError, match="Calls should be empty"):
        funcwcalls._call_record()


@patch("pytest_record_replay.funcwcalls.FunctionWCalls.save")
def test_call_record_saves_calls(save_mock):
    funcwcalls = FunctionWCalls(call_funcs)

    assert funcwcalls._call_record("recorded") == "recorded"

    assert funcwcalls.calls == []
    save_mock.assert_called_once_with(timestamp)


@patch(
    "pytest_record_replay.funcwcalls.FunctionWCalls.files",
    new_callable=PropertyMock,
    return_value=[],
)
def test_call_recall_requires_recording_files(_files_mock):
    funcwcalls = FunctionWCalls(identity)

    with pytest.raises(AssertionError, match="No recorded calls found"):
        funcwcalls._call_recall()


def test_call_recall_loads_files_and_resets_test_case(tmp_path, monkeypatch):
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    events = []

    class Case(unittest.TestCase):
        def setUp(self):
            events.append("setUp")

        def tearDown(self):
            events.append("tearDown")

        def run_case(self):
            call = funcwcalls.calls[0]
            output = MockReplay(call.target, calls=funcwcalls.calls)()
            events.append((self._testMethodName, output))
            return output

    case = Case("run_case")
    funcwcalls = FunctionWCalls(case.run_case)
    funcwcalls.calls[:] = [Call("one", (), {}, "first", post_args=(), post_kwargs={})]
    funcwcalls.save("one")
    funcwcalls.calls[:] = [Call("two", (), {}, "second", post_args=(), post_kwargs={})]
    funcwcalls.save("two")
    funcwcalls.calls.clear()

    outputs = funcwcalls()

    assert outputs is None
    assert [event[1] for event in events if isinstance(event, tuple)] == [
        "first",
        "second",
    ]
    assert events[1:3] == ["tearDown", "setUp"]


def test_test_case_reset_skips_plain_function():
    assert not FunctionWCalls(identity)._TestCaseReset()


def test_test_case_reset_skips_method_on_non_test_case():
    class Example:
        def method(self):
            return None

    assert not FunctionWCalls(Example().method)._TestCaseReset()


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
    funcwcalls = FunctionWCalls(identity)
    funcwcalls.calls.append(
        Call("identity", ("value",), {}, "value", post_args=(None,), post_kwargs={})
    )
    funcwcalls.save("z-last")
    funcwcalls.save("a-first")

    assert [path.name for path in funcwcalls.files] == ["a-first.pkl", "z-last.pkl"]

    funcwcalls.calls.clear()
    funcwcalls._load(funcwcalls.files[0])
    assert funcwcalls.calls == [
        Call("identity", ("value",), {}, "value", post_args=(None,), post_kwargs={})
    ]


def test_pickle_preserves_python_value_types(tmp_path, monkeypatch):
    monkeypatch.setattr(
        FunctionWCalls,
        "path",
        property(lambda self: tmp_path / "recordings"),
    )
    funcwcalls = FunctionWCalls(identity)
    original = Call(
        "identity",
        (b"value",),
        {"tags": {"one", "two"}},
        b"result",
        post_args=(None,),
        post_kwargs={"tags": None},
    )
    funcwcalls.calls.append(original)
    funcwcalls.save("typed-values")

    funcwcalls.calls.clear()
    funcwcalls._load(funcwcalls.files[0])

    assert funcwcalls.calls == [original]
    assert isinstance(funcwcalls.calls[0].args[0], bytes)
    assert isinstance(funcwcalls.calls[0].kwargs["tags"], set)
