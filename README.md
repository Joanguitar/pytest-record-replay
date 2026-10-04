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
