import pytest

from app import stock


def test_reserve_then_release_restores_stock():
    levels = {"pen": 10}
    stock.reserve(levels, "pen", 4)
    stock.release(levels, "pen", 4)
    assert levels["pen"] == 10


def test_reserve_more_than_available_fails():
    with pytest.raises(ValueError):
        stock.reserve({"pen": 1}, "pen", 2)
