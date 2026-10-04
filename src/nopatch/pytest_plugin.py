"""Pytest integration for nopatch."""

import pickle
from pathlib import Path

import pytest

from .mock import _configure_patch


_RECORDINGS_FILE = ".nopatch-recordings.pkl"


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
    path = Path(config.rootpath) / _RECORDINGS_FILE
    if record or not path.exists():
        recordings = {}
    else:
        try:
            with path.open("rb") as stream:
                recordings = pickle.load(stream)
        except (OSError, pickle.PickleError, EOFError) as error:
            raise pytest.UsageError(f"could not load {path}: {error}") from error
    _configure_patch(record, recordings)


def pytest_sessionfinish(session, exitstatus):
    """Persist calls collected during a recording run."""
    if not session.config.getoption("--record"):
        return
    path = Path(session.config.rootpath) / _RECORDINGS_FILE
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary_path.open("wb") as stream:
            pickle.dump(_recordings_for_session(), stream)
        temporary_path.replace(path)
    except OSError as error:
        raise pytest.UsageError(f"could not save {path}: {error}") from error


def _recordings_for_session():
    from .mock import _recordings

    return _recordings


@pytest.fixture
def nopatch_recording(request):
    """Whether this pytest run was started with ``--record``."""
    return request.config.getoption("--record")
