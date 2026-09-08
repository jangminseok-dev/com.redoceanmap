from market.domain.value_objects.sales_unit import QUARTER_MONTHS, monthly_from_quarter


def test_분기_합계를_월로_환산한다():
    assert QUARTER_MONTHS == 3
    assert monthly_from_quarter(370_875_856) == 123_625_285
    assert monthly_from_quarter(0) == 0
    assert monthly_from_quarter(None) is None
