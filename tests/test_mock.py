import pytest

from pytest_replay.mock import MockReplay, MockRecord


def identity(value=None):
    return value


def dependency(value):
    return f"result: {value}"


def test_record_and_recall_keyword_arguments():
    calls = []
    recorder = MockRecord("dependency", dependency, calls=calls)

    assert recorder(value="recorded") == "result: recorded"
    assert MockReplay("dependency", calls=calls)(value="recorded") == (
        "result: recorded"
    )


def test_recall_rejects_keyword_argument_mismatch():
    calls = []
    MockRecord("dependency", dependency, calls=calls)(value="expected")

    with pytest.raises(ValueError, match="Arguments mismatch"):
        MockReplay("dependency", calls=calls)(value="different")


def test_record_rejects_non_dillable_positional_argument():
    recorder = MockRecord("dependency", dependency)
    value = (item for item in ())

    with pytest.raises(ValueError, match="Argument .* is not picklable"):
        recorder(value)


def test_record_rejects_non_dillable_keyword_argument():
    recorder = MockRecord("dependency", dependency)
    value = (item for item in ())

    with pytest.raises(ValueError, match="Keyword argument value=.* is not picklable"):
        recorder(value=value)


def test_record_rejects_non_dillable_output():
    def returns_generator():
        return (item for item in ())

    recorder = MockRecord("dependency", returns_generator)

    with pytest.raises(ValueError, match="Output .* is not picklable"):
        recorder()


def test_recorded_call_deep_copies_args_kwargs_and_output():
    def mutate_inputs_and_return(positional, *, keyword):
        positional.append("during call")
        keyword["items"].append("during call")
        return {"items": ["output"]}

    positional = ["before call"]
    keyword = {"items": ["before call"]}
    calls = []
    recorder = MockRecord(
        "mutate_inputs_and_return", mutate_inputs_and_return, calls=calls
    )

    result = recorder(positional, keyword=keyword)
    result["items"].append("after call")
    positional.append("after call")
    keyword["items"].append("after call")

    assert calls[0].args == (["before call"],)
    assert calls[0].kwargs == {"keyword": {"items": ["before call"]}}
    assert calls[0].output == {"items": ["output"]}


def test_recall_wrong_target_raises_value_error():
    calls = []
    MockRecord("dependency", dependency, calls=calls)(value="expected")

    with pytest.raises(ValueError, match="Target mismatch"):
        MockReplay("different_target", calls=calls)(value="expected")
