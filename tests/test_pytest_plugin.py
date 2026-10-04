pytest_plugins = ["pytester"]


def test_record_option_enables_recording_fixture(pytester):
    pytester.makepyfile(
        """
        def test_recording_mode(nopatch_recording):
            assert nopatch_recording is True
        """
    )

    result = pytester.runpytest("-p", "nopatch.pytest_plugin", "--record", "-q")

    result.assert_outcomes(passed=1)


def test_nomock_classes_record_and_recall_without_calling_function():
    from nopatch import NoMockRecord, NoMockRecall

    invocations = []

    def function(value, suffix="!"):
        invocations.append((value, suffix))
        return f"{value}{suffix}"

    recorder = NoMockRecord(function)
    assert recorder("hello", suffix="?") == "hello?"
    assert invocations == [("hello", "?")]
    assert len(recorder.records) == 1

    recall = NoMockRecall(recorder)
    assert recall("hello", suffix="?") == "hello?"
    assert invocations == [("hello", "?")]


def test_nomock_recall_rejects_different_input():
    import pytest
    from nopatch import NoMockRecord, NoMockRecall

    recorder = NoMockRecord(lambda value: value * 2)
    recorder(3)
    recall = NoMockRecall(recorder)

    with pytest.raises(AssertionError, match="does not match recording"):
        recall(4)


def test_recording_fixture_defaults_to_false(pytester):
    pytester.makepyfile(
        """
        def test_recall_mode(nopatch_recording):
            assert nopatch_recording is False
        """
    )

    result = pytester.runpytest("-p", "nopatch.pytest_plugin", "-q")

    result.assert_outcomes(passed=1)