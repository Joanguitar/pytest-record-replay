from nopatch import nopatch


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
    assert multiply(21) == 42


@nopatch(f"{__name__}.describe")
def test_description_is_recorded():
    assert describe("sample") == {"name": "sample", "active": True}

@nopatch(f"{__name__}.multiply")
@nopatch(f"{__name__}.describe")
def test_multiple_functions_are_recorded():
    run_count_old = run_count.copy()
    assert multiply(10) == 20
    assert describe("test") == {"name": "test", "active": True}
