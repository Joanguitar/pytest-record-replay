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


def test_recording_fixture_defaults_to_false(pytester):
    pytester.makepyfile(
        """
        def test_recall_mode(nopatch_recording):
            assert nopatch_recording is False
        """
    )

    result = pytester.runpytest("-p", "nopatch.pytest_plugin", "-q")

    result.assert_outcomes(passed=1)