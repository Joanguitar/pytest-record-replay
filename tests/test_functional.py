from unittest.mock import Mock, patch

from pytest_replay.decorators import nodecorator, replay, recording


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


@replay(f"{__name__}.multiply")
def test_multiply_is_recorded():
    run_count_old = run_count.copy()
    assert multiply(21) == 42
    assert run_count["multiply"] == run_count_old["multiply"] + recording()


@replay(f"{__name__}.describe")
def test_description_is_recorded():
    run_count_old = run_count.copy()
    assert describe("sample") == {"name": "sample", "active": True}
    assert run_count["describe"] == run_count_old["describe"] + recording()


@replay(f"{__name__}.multiply")
@replay(f"{__name__}.describe")
def test_multiple_functions_are_recorded():
    run_count_old = run_count.copy()
    assert multiply(10) == 20
    assert describe("test") == {"name": "test", "active": True}
    for key, value in run_count.items():
        assert value == run_count_old[key] + recording()


@patch("pytest_replay.funcwcalls.FunctionWCalls._save")  # Don't actually save
def test_recording_will_always_save(mock_save: Mock):
    @replay(f"{__name__}.multiply")
    @replay(f"{__name__}.describe")
    @nodecorator(record=True)
    def same_function():
        assert multiply(10) == 20
        assert describe("test")

    same_function()

    mock_save.assert_called_once()
