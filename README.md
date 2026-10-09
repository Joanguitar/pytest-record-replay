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

## `@replay`

Import `replay` and decorate a test with the dotted name of the dependency it
uses. The name should refer to where the dependency is looked up by the code
under test.

```python
from pytest_replay import replay
from myapp import client


@replay("myapp.client.fetch_data")
def test_fetch_data():
    assert client.fetch_data("item-1") == {"id": "item-1"}
```

When recording, `fetch_data` runs normally and pytest-replay saves its inputs
and output. On replay, it returns the saved output and checks that the inputs
match. Apply `@replay` more than once to record or replay multiple dependencies:

```python
@replay("myapp.client.fetch_data")
@replay("myapp.clock.now")
def test_report():
    ...
```

## `@nodecorator`

Use `@nodecorator` when composing a test wrapper with `@replay`. It adds
recording/replay metadata to the test without patching a dependency itself.
Specify `record` or `file` here to override the default mode or choose a
recording file for that test.

```python
from pathlib import Path
from pytest_replay import nodecorator, replay
from myapp import client


@replay("myapp.client.fetch_data")
@nodecorator(record=True, file=Path("test-data/fetch.pkl"))
def test_fetch():
    assert client.fetch_data("item-1") == {"id": "item-1"}
```

If `record` is omitted, `nodecorator` uses the current pytest mode: recording
with `--record`, replaying without it. When using both decorators, place
`@nodecorator` closest to the function so it is applied before `@replay`.

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
