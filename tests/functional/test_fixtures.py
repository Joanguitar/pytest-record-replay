from pathlib import Path
import sys

import pytest

from pytest_record_replay.decorators import patch_replay, set_replay
from pytest_record_replay.mock import MockR
from pytest_record_replay.util import recording

sys.path.append(str(Path(__file__).parent.parent))
from helpers import counting, multiply


@pytest.fixture
def mock_multiply():
    with patch_replay(f"{__name__}.multiply") as mock_multiply:
        yield mock_multiply


@set_replay()
def test_fixture(mock_multiply: MockR, replay_recording: bool):
    with counting() as count:
        assert multiply(1) == 2
        mock_multiply.assert_called_once_with(1)
        assert count["multiply"] == replay_recording
        assert count["multiply"] == recording()
