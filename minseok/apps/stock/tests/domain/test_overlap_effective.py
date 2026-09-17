"""겹침 보정 유효 표본."""


def test_겹치는_창은_지평으로_나눈_유효_표본으로_구간을_넓힌다():
    from stock.domain.value_objects.backtest_report import overlap_effective, wilson_bounds
    assert overlap_effective(60, 500, 5) == (12.0, 100.0)
    raw_lo, raw_hi = wilson_bounds(60, 500)
    eff_lo, eff_hi = wilson_bounds(*overlap_effective(60, 500, 5))
    assert eff_lo < raw_lo and eff_hi > raw_hi  # 같은 적중률, 더 넓은 구간
    assert overlap_effective(3, 10, 0) == (3.0, 10.0)  # 지평 0 방어
