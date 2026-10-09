"""Pytest integration for pytest-record-replay."""

import pytest


def pytest_addoption(parser):
    """Register the command-line option that enables recording mode."""
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="enable recording mode for pytest-record-replay tests",
    )


def pytest_configure(config):
    """Set pytest-record-replay's recording mode from pytest's ``--record`` option."""
    record = config.getoption("--record")
    from pytest_record_replay.util import _configure_patch

    _configure_patch(record)


@pytest.fixture
def replay_recording():
    """Provide the active recording mode to a test as a boolean."""
    from pytest_record_replay.util import recording

    return recording()
