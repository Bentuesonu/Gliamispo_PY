import pytest
from gliamispo.models.eighths import Eighths, scene_duration


class TestEighthsInit:
    def test_zero(self):
        e = Eighths()
        assert e.whole == 0
        assert e.eighths == 0

    def test_simple(self):
        e = Eighths(2, 3)
        assert e.whole == 2
        assert e.eighths == 3

    def test_overflow(self):
        e = Eighths(1, 10)
        assert e.whole == 2
        assert e.eighths == 2

    def test_exact_overflow(self):
        e = Eighths(0, 16)
        assert e.whole == 2
        assert e.eighths == 0


class TestEighthsFromDecimal:
    def test_integer(self):
        e = Eighths.from_decimal(3.0)
        assert e.whole == 3
        assert e.eighths == 0

    def test_half(self):
        e = Eighths.from_decimal(1.5)
        assert e.whole == 1
        assert e.eighths == 4

    def test_three_eighths(self):
        e = Eighths.from_decimal(1.375)
        assert e.whole == 1
        assert e.eighths == 3

    def test_seven_eighths(self):
        e = Eighths.from_decimal(2.875)
        assert e.whole == 2
        assert e.eighths == 7


class TestEighthsFromString:
    def test_whole_and_fraction(self):
        e = Eighths.from_string("1 3/8")
        assert e.whole == 1
        assert e.eighths == 3

    def test_fraction_only(self):
        e = Eighths.from_string("5/8")
        assert e.whole == 0
        assert e.eighths == 5

    def test_whole_only(self):
        e = Eighths.from_string("4")
        assert e.whole == 4
        assert e.eighths == 0

    def test_whitespace(self):
        e = Eighths.from_string("  2 1/8  ")
        assert e.whole == 2
        assert e.eighths == 1

    def test_quarter(self):
        e = Eighths.from_string("1/4")
        assert e.whole == 0
        assert e.eighths == 2


class TestEighthsArithmetic:
    def test_total_eighths(self):
        e = Eighths(2, 3)
        assert e.total_eighths == 19

    def test_sub(self):
        a = Eighths(3, 5)
        b = Eighths(1, 2)
        result = a - b
        assert result.whole == 2
        assert result.eighths == 3

    def test_sub_with_borrow(self):
        a = Eighths(2, 1)
        b = Eighths(1, 5)
        result = a - b
        assert result.whole == 0
        assert result.eighths == 4

    def test_eq(self):
        assert Eighths(1, 4) == Eighths(1, 4)
        assert Eighths(0, 8) == Eighths(1, 0)

    def test_neq(self):
        assert not (Eighths(1, 3) == Eighths(1, 4))


class TestEighthsRepr:
    def test_zero_eighths(self):
        assert repr(Eighths(3, 0)) == "3"

    def test_with_eighths(self):
        assert repr(Eighths(1, 3)) == "1 3/8"

    def test_zero_whole(self):
        assert repr(Eighths(0, 5)) == "0 5/8"


class TestSceneDuration:
    def test_simple(self):
        d = scene_duration(1.0, 1.375)
        assert d == Eighths(0, 3)

    def test_multi_page(self):
        d = scene_duration(1.125, 2.875)
        assert d == Eighths(1, 6)

    def test_zero_duration(self):
        d = scene_duration(1.0, 1.0)
        assert d == Eighths(0, 0)
