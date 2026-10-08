# nopatch

`nopatch` records calls to dependencies during a test run, then replays those
calls on later runs. Use it to test code that depends on services or other
external behavior without calling those dependencies every time.

## Install

```bash
python -m pip install nopatch
```

After installation, pytest loads the nopatch plugin automatically. Use
`pytest --record` to record dependency calls. Run `pytest` without that option
to replay them.

To install a local checkout for development, including the test dependencies:

```bash
python -m pip install -e ".[test]"
```

## `@nopatch`

Decorate a test with the dotted name of the dependency it uses. The name should
refer to where the dependency is looked up by the code under test.

```python
from nopatch import nopatch
from myapp import client


@nopatch("myapp.client.fetch_data")
def test_fetch_data():
    assert client.fetch_data("item-1") == {"id": "item-1"}
```

When recording, `fetch_data` runs normally and nopatch saves its inputs and
output. On replay, nopatch returns the saved output and checks that the inputs
match. Apply `@nopatch` more than once to record or replay multiple
dependencies:

```python
@nopatch("myapp.client.fetch_data")
@nopatch("myapp.clock.now")
def test_report():
    ...
```

## `@nodecorator`

Use `@nodecorator` when composing a test wrapper with `@nopatch`. It adds
recording/replay metadata to the test without patching a dependency itself.
Specify `record` or `file` here to override the default mode or choose a
recording file for that test.

```python
from pathlib import Path
from nopatch import nodecorator, nopatch
from myapp import client


@nopatch("myapp.client.fetch_data")
@nodecorator(record=True, file=Path("test-data/fetch.pkl"))
def test_fetch():
    assert client.fetch_data("item-1") == {"id": "item-1"}
```

If `record` is omitted, `nodecorator` uses the current pytest mode: recording
with `--record`, replaying without it. When using both decorators, place
`@nodecorator` closest to the function so it is applied before `@nopatch`.

## Check recording mode

Use `recording()` in Python code or request pytest's `nopatch_recording`
fixture in a test. Both report whether the current run is in recording mode.

```python
from nopatch import recording


def test_result():
    result = run_operation()
    assert result is not None
    if recording():
        assert operation_was_called()
```

```python
def test_result(nopatch_recording):
    result = run_operation()
    assert result is not None
    if nopatch_recording:
        assert operation_was_called()
```

The fixture is useful when a test needs to make assertions that differ between
recording and replay runs. The default mode is replay; pass `--record` to
pytest to enable recording.
