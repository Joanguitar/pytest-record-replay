"""Pytest integration for nopatch."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="enable recording mode for nopatch tests",
    )


def pytest_configure(config):
    """Configure wrappers and load the saved call history for this run."""
    record = config.getoption("--record")
    from .mock import _configure_patch

    _configure_patch(record)


@pytest.fixture
def nopatch_recording(request):
    """Whether this pytest run was started with ``--record``."""
    return request.config.getoption("--record")
