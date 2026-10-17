from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from helpers import counting, describe, multiply

from unittest import TestCase

from pytest_record_replay.decorators import patch_replay
from pytest_record_replay.util import recording


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
