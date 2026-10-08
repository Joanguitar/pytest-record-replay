"""Pytest integration for nopatch."""

import pytest


def pytest_addoption(parser):
    """Register the command-line option that enables recording mode."""
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="enable recording mode for nopatch tests",
    )


def pytest_configure(config):
    """Set nopatch's recording mode from pytest's ``--record`` option."""
    record = config.getoption("--record")
    from nopatch.util import _configure_patch

    _configure_patch(record)


@pytest.fixture
def nopatch_recording():
    """Provide the active recording mode to a test as a boolean."""
    from nopatch.util import recording

    return recording()
