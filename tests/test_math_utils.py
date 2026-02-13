from src.math_utils import add


def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative_and_positive():
    assert add(-1, 1) == 0


def test_add_floats():
    assert abs(add(0.1, 0.2) - 0.30000000000000004) < 1e-12
