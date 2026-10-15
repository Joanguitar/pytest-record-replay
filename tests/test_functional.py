from unittest import TestCase
from unittest.mock import Mock, patch

from pytest_record_replay.util import recording
from pytest_record_replay.decorators import (
    set_replay,
    patch_replay,
)
from helpers import counting, describe, multiply


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


def example():
    with counting() as count:
        assert multiply(10) == 20
        assert describe("test") == {"name": "test", "active": True}
        for key in ["multiply", "describe"]:
            assert count[key] == recording()


@patch_replay(f"{__name__}.multiply")
@patch_replay(f"{__name__}.describe")
class TestDecoratedClass(TestCase):
    """Decorated class"""

    def test_example(self):
        example()


class TestDecoratedMethod(TestCase):
    """Class with decorated methods"""

    @patch_replay(f"{__name__}.multiply")
    @patch_replay(f"{__name__}.describe")
    def test_example(self):
        example()


@patch_replay(f"{__name__}.multiply")
class TestDecoratedClassAndMethod(TestCase):
    """Decorated class with decorated methods"""

    @patch_replay(f"{__name__}.describe")
    def test_example(self):
        example()


class TestAPosteriori(TestCase):
    """Class with methods that are decorated a posteriori"""

    def test_example(self):
        example()


TestAPosteriori.test_example = patch_replay(f"{__name__}.multiply")(
    patch_replay(f"{__name__}.describe")(TestAPosteriori.test_example)
)
