# pytest-replay

`pytest-replay` records calls to dependencies during a test run, then replays
those calls on later runs. Use it to test code that depends on services or
other external behavior without calling those dependencies every time.

## Install

```bash
python -m pip install pytest-replay
```

After installation, pytest loads the pytest-replay plugin automatically. Use
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
from pytest_replay import patch_replay
from myapp import client


@patch_replay("myapp.client.fetch_data")
def test_fetch_data():
    assert client.fetch_data("item-1") == {"id": "item-1"}
```

When recording, `fetch_data` runs normally and pytest-replay saves its inputs
and output. On replay, it returns the saved output and checks that the inputs
match. Apply `@patch_replay` more than once to record or replay multiple
dependencies:

```python
@patch_replay("myapp.client.fetch_data")
@patch_replay("myapp.clock.now")
def test_report():
    ...
```

## `@set_replay`

Use `@set_replay` to configure recording/replay metadata on a test without
patching a dependency itself. Specify `record` or `file` to override the
current pytest mode or choose a recording file for that test. It is also useful
when composing another test wrapper with `@patch_replay`.

```python
from pathlib import Path
from pytest_replay import patch_replay, set_replay
from myapp import client


@patch_replay("myapp.client.fetch_data")
@set_replay(record=True, file=Path("test-data/fetch.pkl"))
def test_fetch():
    assert client.fetch_data("item-1") == {"id": "item-1"}
```

If `record` is omitted, `set_replay` uses the current pytest mode: recording
with `--record`, replaying without it. When using both decorators, place
`@set_replay` closest to the function so it is applied before `@patch_replay`.

## Check recording mode

Use `recording()` in Python code or request pytest's `replay_recording`
fixture in a test. Both report whether the current run is in recording mode.

```python
from pytest_replay import recording


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
