from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).parent.parent))
from helpers import counting, describe, multiply

from unittest.mock import Mock, patch

from pytest_record_replay.decorators import patch_replay, set_replay
from pytest_record_replay.util import recording


file = Path(__file__).parent / "resources_pytest_record_replay" / "decorated_function.pkl"

def _function():
    with counting() as count:
        assert multiply(10) == 20
        assert describe("test")
        for key in ["multiply", "describe"]:
            assert count[key] == recording()
    return True

@patch_replay(f"{__name__}.multiply")
def test_multiply_is_recorded():
    with counting() as count:
        assert multiply(21) == 42
        assert count["multiply"] == recording()


@patch_replay(f"{__name__}.describe")
def test_description_is_recorded():
    with counting() as count:
        assert describe("sample") == {"name": "sample", "active": True}
        assert count["describe"] == recording()


@patch_replay(f"{__name__}.multiply")
@patch_replay(f"{__name__}.describe")
def test_multiple_functions_are_recorded():
    with counting() as count:
        assert multiply(10) == 20
        assert describe("test") == {"name": "test", "active": True}
        for key in ["multiply", "describe"]:
            assert count[key] == recording()


@patch("pytest_record_replay.funcwcalls.FunctionWCalls._save")
def test_recording_will_always_save(mock_save: Mock):
    @set_replay(record=True)
    @patch_replay(f"{__name__}.multiply")
    @patch_replay(f"{__name__}.describe")
    @set_replay(file=file)
    def recorder(): return _function()

    assert recorder()

    mock_save.assert_called_once_with(file)

def test_record_replay():
    @patch_replay(f"{__name__}.multiply")
    @patch_replay(f"{__name__}.describe")
    @set_replay(file=file)
    def _func(): return _function()
    for _r in [True, False]:
        r_func = set_replay(record=_r)(_func)
        assert r_func.record == _r
        assert r_func()
        assert len(r_func.calls) == 2 * _r
        assert len(_func.calls) == 0
        with pytest.raises(AttributeError):
            set_replay(record=not _r)(r_func)