# nopatch

Record/recall logic for testing, integrated with pytest.

## Install

```bash
python -m pip install -e .
```

Pytest loads the `nopatch` plugin automatically after installation. Use
`--record` to enable recording mode; without it, recording mode is disabled.

```bash
pytest --record
```

Tests can inspect the mode with the `nopatch_recording` fixture:

```python
def test_example(nopatch_recording):
	if nopatch_recording:
		...  # record behavior
	else:
		...  # recall behavior
```

## Record and recall a callable

`NoMockRecord` calls the original function and saves each call in order.
`NoMockRecall` replays those outputs, checking that each input matches the
recorded call without invoking the original function again.

```python
from nopatch import NoMockRecord, NoMockRecall

recording = NoMockRecord(fetch_data)
first_result = recording("item-1")

recall = NoMockRecall(recording)
assert recall("item-1") == first_result
```
