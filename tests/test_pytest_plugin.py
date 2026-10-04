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

    recall = NoMockRecall(function, recording=recorder.records, name=recorder.name)
    assert recall("hello", suffix="?") == "hello?"
    assert invocations == [("hello", "?")]


def test_nomock_recall_rejects_different_input():
    import pytest
    from nopatch import NoMockRecord, NoMockRecall

    recorder = NoMockRecord(lambda value: value * 2)
    recorder(3)
    recall = NoMockRecall(
        recorder.function, recording=recorder.records, name=recorder.name
    )

    with pytest.raises(AssertionError, match="does not match recording"):
        recall(4)


def test_patch_uses_record_or_recall_mode(monkeypatch):
    import sys
    import types

    from nopatch import NoMockRecord, NoMockRecall, patch
    from nopatch.mock import _configure_patch

    module = types.ModuleType("nopatch_patch_target")
    invocations = []
    module.target = lambda value: invocations.append(value) or value * 2
    monkeypatch.setitem(sys.modules, module.__name__, module)
    recordings = {}

    try:
        _configure_patch(True, recordings)
        with patch("nopatch_patch_target.target") as recorder:
            assert isinstance(recorder, NoMockRecord)
            assert module.target(6) == 12
        with patch("nopatch_patch_target.target"):
            assert module.target(7) == 14

        _configure_patch(False, recordings)
        with patch("nopatch_patch_target.target") as recall:
            assert isinstance(recall, NoMockRecall)
            assert module.target(6) == 12
        with patch("nopatch_patch_target.target"):
            assert module.target(7) == 14

        assert invocations == [6, 7]
    finally:
        _configure_patch(False, {})


def test_record_flag_persists_results_for_recall(pytester):
    pytester.makepyfile(service='''
        def fetch(key):
            return "recorded:" + key
    ''')
    pytester.makepyfile(test_client='''
        import service
        from nopatch import patch

        def test_fetch():
            with patch("service.fetch"):
                assert service.fetch("item") == "recorded:item"
    ''')

    record_result = pytester.runpytest_subprocess(
        "-p", "nopatch.pytest_plugin", "--record", "-q"
    )
    record_result.assert_outcomes(passed=1)

    pytester.makepyfile(service='''
        def fetch(key):
            return "live:" + key
    ''')
    recall_result = pytester.runpytest_subprocess(
        "-p", "nopatch.pytest_plugin", "-q"
    )
    recall_result.assert_outcomes(passed=1)


def test_patch_records_and_replays_instance_methods(monkeypatch):
    import sys
    import types

    from nopatch import patch
    from nopatch.mock import _configure_patch

    module = types.ModuleType("nopatch_method_target")
    exec(
        "class Service:\n"
        "    invocations = []\n"
        "    def fetch(self, value):\n"
        "        self.invocations.append(value)\n"
        "        return value * 2\n",
        module.__dict__,
    )
    monkeypatch.setitem(sys.modules, module.__name__, module)
    recordings = {}

    try:
        _configure_patch(True, recordings)
        with patch("nopatch_method_target.Service.fetch"):
            assert module.Service().fetch(3) == 6

        _configure_patch(False, recordings)
        with patch("nopatch_method_target.Service.fetch"):
            assert module.Service().fetch(3) == 6

        assert module.Service.invocations == [3]
    finally:
        _configure_patch(False, {})


def test_recording_fixture_defaults_to_false(pytester):
    pytester.makepyfile(
        """
        def test_recall_mode(nopatch_recording):
            assert nopatch_recording is False
        """
    )

    result = pytester.runpytest("-p", "nopatch.pytest_plugin", "-q")

    result.assert_outcomes(passed=1)