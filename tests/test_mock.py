import pytest

from pytest_record_replay.util import record
from pytest_record_replay.mock import MockR
from helpers import dependency


def test_record_and_recall_keyword_arguments():
    calls = []

    mockr = MockR(f"{__name__}.dependency", calls=calls)
    with record(True):
        assert mockr(value="recorded") == "result: recorded"
    with record(False):
        assert mockr(value="recorded") == ("result: recorded")


def test_recall_rejects_keyword_argument_mismatch():
    calls = []
    mockr = MockR(f"{__name__}.dependency", calls=calls)
    with record(True):
        mockr(value="expected")

    with pytest.raises(ValueError, match="Arguments mismatch"):
        with record(False):
            mockr(value="different")


def test_record_rejects_non_dillable_positional_argument():
    mockr = MockR("dependency", dependency)
    value = (item for item in ())

    with pytest.raises(ValueError, match="Argument .* is not picklable"):
        with record(True):
            mockr(value)


def test_record_rejects_non_dillable_keyword_argument():
    mockr = MockR("dependency", dependency)
    value = (item for item in ())

    with pytest.raises(ValueError, match="Keyword argument value=.* is not picklable"):
        with record(True):
            mockr(value=value)


def test_record_rejects_non_dillable_output():
    def returns_generator():
        return (item for item in ())

    mockr = MockR("dependency", returns_generator)

    with pytest.raises(ValueError, match="Output .* is not picklable"):
        with record(True):
            mockr()


def test_recorded_call_deep_copies_args_kwargs_and_output():
    def mutate_inputs_and_return(positional, *, keyword):
        positional.append("during call")
        keyword["items"].append("during call")
        return {"items": ["output"]}

    positional = ["before call"]
    keyword = {"items": ["before call"]}
    calls = []
    recorder = MockR("mutate_inputs_and_return", mutate_inputs_and_return, calls=calls)

    with record(True):
        result = recorder(positional, keyword=keyword)
    result["items"].append("after call")
    positional.append("after call")
    keyword["items"].append("after call")

    assert calls[0].args == (["before call"],)
    assert calls[0].kwargs == {"keyword": {"items": ["before call"]}}
    assert calls[0].output == {"items": ["output"]}


def test_recall_wrong_target_raises_value_error():
    calls = []
    mockr = MockR("helpers.dependency", calls=calls)
    with record(True):
        mockr(value="expected")

    with pytest.raises(ValueError, match="Target mismatch"):
        with record(False):
            MockR("helpers.identity", calls=calls)(value="expected")
