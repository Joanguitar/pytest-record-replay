"""Pytest integration for nopatch."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="enable recording mode for nopatch tests",
    )


@pytest.fixture
def nopatch_recording(request):
    """Whether this pytest run was started with ``--record``."""
    return request.config.getoption("--record")