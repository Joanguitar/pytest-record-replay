from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from helpers import counting, multiply

from pytest_record_replay.decorators import patch_replay, set_replay
from pytest_record_replay.util import recording


@set_replay()
def test_patch_mid_function():
    with counting() as count:
        assert multiply(1) == 2
        with patch_replay(f"{__name__}.multiply") as mock_multiply:
            assert multiply(2) == 4
            mock_multiply.assert_called_once()
        assert multiply(3) == 6
        assert count["multiply"] == 2 + recording()
