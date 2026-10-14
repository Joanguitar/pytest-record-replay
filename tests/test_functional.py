from unittest import TestCase
from unittest.mock import Mock, patch

from pytest_record_replay.decorators import (
    _decorate_class,
    set_replay,
    patch_replay,
    recording,
)


run_count = {
    "multiply": 0,
    "describe": 0,
}


def multiply(value):
    run_count["multiply"] += 1
    return value * 2


def describe(name):
    run_count["describe"] += 1
    return {"name": name, "active": True}


@patch_replay(f"{__name__}.multiply")
def test_multiply_is_recorded():
    run_count_old = run_count.copy()
    assert multiply(21) == 42
    assert run_count["multiply"] == run_count_old["multiply"] + recording()


@patch_replay(f"{__name__}.describe")
def test_description_is_recorded():
    run_count_old = run_count.copy()
    assert describe("sample") == {"name": "sample", "active": True}
    assert run_count["describe"] == run_count_old["describe"] + recording()


@patch_replay(f"{__name__}.multiply")
@patch_replay(f"{__name__}.describe")
def test_multiple_functions_are_recorded():
    run_count_old = run_count.copy()
    assert multiply(10) == 20
    assert describe("test") == {"name": "test", "active": True}
    for key, value in run_count.items():
        assert value == run_count_old[key] + recording()


@patch("pytest_record_replay.funcwcalls.FunctionWCalls._save")  # Don't actually save
def test_recording_will_always_save(mock_save: Mock):
    @patch_replay(f"{__name__}.multiply")
    @patch_replay(f"{__name__}.describe")
    @set_replay(record=True)
    def same_function():
        assert multiply(10) == 20
        assert describe("test")

    same_function()

    mock_save.assert_called_once()


@patch_replay(f"{__name__}.multiply")
@patch_replay(f"{__name__}.describe")
class TestClass(TestCase):
    def test_multiple_functions_are_recorded(self):
        run_count_old = run_count.copy()
        assert multiply(10) == 20
        assert describe("test") == {"name": "test", "active": True}
        for key, value in run_count.items():
            assert value == run_count_old[key] + recording()


@patch("pytest_record_replay.funcwcalls.FunctionWCalls._save")  # Don't actually save
def test_recording_testcase_will_always_save(mock_save: Mock):
    @patch_replay(f"{__name__}.multiply")
    @patch_replay(f"{__name__}.describe")
    @set_replay(record=True)
    class RecordingTestClass:
        def test_multiple_functions_are_recorded(self):
            run_count_old = run_count.copy()
            assert multiply(10) == 20
            assert describe("test") == {"name": "test", "active": True}
            for key, value in run_count.items():
                assert value == run_count_old[key] + recording()

    recording_test = RecordingTestClass()
    counter = 0

    def _eval_method(method):
        nonlocal counter
        print(method.__name__)
        method(recording_test)
        mock_save.assert_called_once()
        mock_save.reset_mock()
        counter += 1

    _decorate_class(RecordingTestClass, _eval_method)
    assert counter > 0
