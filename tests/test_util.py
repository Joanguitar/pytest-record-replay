from threading import Thread
from time import sleep
from typing import Dict, Optional

import pytest
from pytest_record_replay.util import get_calls, record, recording


def test_recording_race_condition():
    was_recording: Dict[str, Optional[bool]] = {
        "func1": None,
        "func2": None,
    }

    def func1():
        with record(True):
            sleep(0.1)
            was_recording["func1"] = recording()

    def func2():
        with record(False):
            sleep(0.2)
            was_recording["func2"] = recording()

    thread1 = Thread(target=func1)
    thread2 = Thread(target=func2)

    thread1.start()
    sleep(0.05)
    thread2.start()

    thread1.join()
    thread2.join()

    assert was_recording["func1"]
    assert not was_recording["func2"]


def test_get_calls_outside_of_context():
    pytest.raises(RuntimeError, get_calls)
