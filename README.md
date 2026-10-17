# pytest-record-replay

`pytest-record-replay` records calls to dependencies during a test run, then replays
those calls on later runs. Use it to test code that depends on services or
other external behavior without calling those dependencies every time.

## Install

```bash
python -m pip install pytest-record-replay
```

After installation, pytest loads the pytest-record-replay plugin automatically. Use
`pytest --record` to record dependency calls. Run `pytest` without that option
to replay them.

To install a local checkout for development, including the test dependencies:

```bash
python -m pip install -e ".[test]"
```

## `@patch_replay`

Import `patch_replay` and decorate a test with the dotted name of the dependency
it uses. The name should refer to where the dependency is looked up by the code
under test.

```python
from pytest_record_replay import patch_replay
from myapp import client


@patch_replay("myapp.client.fetch_data")
def test_fetch_data():
    assert client.fetch_data("item-1") == {"id": "item-1"}
```

When recording, `fetch_data` runs normally and pytest-record-replay saves its inputs
and output. On replay, it returns the saved output and checks that the inputs
match. Apply `@patch_replay` more than once to record or replay multiple
dependencies:

```python
@patch_replay("myapp.client.fetch_data")
@patch_replay("myapp.clock.now")
def test_report():
    ...
```

### Use `patch_replay` as a context manager

Use `patch_replay` in a `with` block to patch a dependency for only part of a
test. The context manager yields a mock, so you can make assertions about the
calls while the patch is active. Decorate the test with `@set_replay()` so the
calls are saved during recording and loaded during replay:

```python
from pytest_record_replay import patch_replay, set_replay
from myapp import client


@set_replay()
def test_fetch_data():
    with patch_replay("myapp.client.fetch_data") as mock_fetch:
        assert client.fetch_data("item-1") == {"id": "item-1"}
        mock_fetch.assert_called_once_with("item-1")
```

The patch is removed when the `with` block exits. As with the decorator, use
the dotted name where the code under test looks up the dependency.

### Use `patch_replay` as a fixture

If several tests need the same patch, wrap it in a pytest fixture. Yielding the
mock keeps the patch active for the test and automatically removes it when the
fixture finishes:

```python
import pytest
from pytest_record_replay import patch_replay, set_replay
from myapp import client


@pytest.fixture
def fetch_data_mock():
    with patch_replay("myapp.client.fetch_data") as mock_fetch:
        yield mock_fetch


@set_replay()
def test_fetch_data(fetch_data_mock):
    assert client.fetch_data("item-1") == {"id": "item-1"}
    fetch_data_mock.assert_called_once_with("item-1")
```

See the [functional tests](tests/functional/) for runnable examples of decorating functions, TestCase, and using the context-manager and fixture patterns.

## `@set_replay`

Use `@set_replay` to configure recording/replay metadata on a test without
patching a dependency itself. Specify `record` or `file` to override the
current pytest mode or choose a recording file for that test. It is also useful
when composing another test wrapper with `@patch_replay`.

```python
from pathlib import Path
from pytest_record_replay import patch_replay, set_replay
from myapp import client


@patch_replay("myapp.client.fetch_data")
@set_replay(record=True, file=Path("test-data/fetch.pkl"))
def test_fetch():
    assert client.fetch_data("item-1") == {"id": "item-1"}
```

If `record` is omitted, `set_replay` uses the current pytest mode: recording
with `--record`, replaying without it. When using both decorators, place
`@set_replay` closest to the function so it is applied before `@patch_replay`.

## Patching classes

You can also decorate a test class. Each callable method whose name starts
with `test` receives the patch, so the class can share dependency patches
across its tests:

```python
@patch_replay("myapp.client.fetch_data")
@set_replay(file=Path("/path/to/my/file.pkl"))
class TestClient:
    def test_fetch_data(self):
        assert client.fetch_data("item-1") == {"id": "item-1"}
```

Stack class decorators to patch multiple dependencies for each test method.

## Check recording mode

Use `recording()` in Python code or request pytest's `replay_recording`
fixture in a test. Both report whether the current run is in recording mode.

```python
from pytest_record_replay import recording


def test_result():
    result = run_operation()
    assert result is not None
    if recording():
        assert operation_was_called()
```

```python
def test_result(replay_recording):
    result = run_operation()
    assert result is not None
    if replay_recording:
        assert operation_was_called()
```

The fixture is useful when a test needs to make assertions that differ between
recording and replay runs. The default mode is replay; pass `--record` to
pytest to enable recording.
