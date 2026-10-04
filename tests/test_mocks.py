from nopatch import NoMockRecord, NoMockRecall


def echo(x):
    return x


def echo_upper(x: str) -> str:
    return x.upper()


def test_record_normal():
    calls = []
    inputs = (1, "Hi", 3.14, "hello")
    for record in (True, False):
        if record:
            echo_mock = NoMockRecord(target="echo", function=echo, calls=calls)
            echo_upper_mock = NoMockRecord(
                target="echo_upper", function=echo_upper, calls=calls
            )
        else:
            echo_mock = NoMockRecall(target="echo", calls=calls)
            echo_upper_mock = NoMockRecall(target="echo_upper", calls=calls)
        n_calls = 0
        for _input in inputs:
            assert echo_mock(_input) == _input
            n_calls += 1
            if isinstance(_input, str):
                assert echo_upper_mock(_input) == _input.upper()
                n_calls += 1
        if record:
            assert len(calls) == n_calls
        else:
            assert len(calls) == 0


def test_record_target_mismatch():
    calls = []
    echo_mock = NoMockRecord(target="echo", function=echo, calls=calls)
    echo_mock("hello")
    echo_recall = NoMockRecall(target="echo_upper", calls=calls)
    try:
        echo_recall("hello")
    except ValueError as e:
        assert "Target mismatch" in str(e)
    else:
        assert False, "Expected ValueError for target mismatch"


def test_record_mismatch():
    calls = []
    echo_mock = NoMockRecord(target="echo", function=echo, calls=calls)
    echo_mock("hello")
    echo_recall = NoMockRecall(target="echo", calls=calls)
    try:
        echo_recall("world")
    except ValueError as e:
        assert "Arguments mismatch" in str(e)
    else:
        assert False, "Expected ValueError for argument mismatch"
