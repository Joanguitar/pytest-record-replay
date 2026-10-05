from nopatch import nopatch, recording


run_count = {
    "multiply": 0,
    "describe": 0,
}

def multiply(value):
    run_count["multiply"] += 1
    return value * 2


def describe(name):
    run_count["describe"] += 1
    return {"name": name, "active": True}


@nopatch(f"{__name__}.multiply")
def test_multiply_is_recorded():
    run_count_old = run_count.copy()
    assert multiply(21) == 42
    assert run_count["multiply"] == run_count_old["multiply"] + recording()


@nopatch(f"{__name__}.describe")
def test_description_is_recorded():
    run_count_old = run_count.copy()
    assert describe("sample") == {"name": "sample", "active": True}
    assert run_count["describe"] == run_count_old["describe"] + recording()

@nopatch(f"{__name__}.multiply")
@nopatch(f"{__name__}.describe")
def test_multiple_functions_are_recorded():
    run_count_old = run_count.copy()
    assert multiply(10) == 20
    assert describe("test") == {"name": "test", "active": True}
    for key, value in run_count.items():
        assert value == run_count_old[key] + recording()
