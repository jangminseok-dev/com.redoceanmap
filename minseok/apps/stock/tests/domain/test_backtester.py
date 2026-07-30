import pytest

from stock.domain.entities.outlook import Direction, Outlook
from stock.domain.services.backtester import Backtester


class _FixedPredictor:
    """항상 같은 방향을 내는 스텁 — 채점(회계) 로직만 검증한다."""

    def __init__(self, direction: Direction) -> None:
        self._direction = direction

    def predict(self, indicators, sentiment, config) -> Outlook:
        return Outlook(direction=self._direction, confidence=1.0)


def _series(values: list[float]) -> tuple[list[float], list[float], list[float]]:
    return values, [v - 1.0 for v in values], [v + 1.0 for v in values]


RISING = [float(100 + i) for i in range(100)]


def test_상승장에서_항상_UP이면_전부_적중():
    closes, lows, highs = _series(RISING)
    report = Backtester(predictor=_FixedPredictor(Direction.UP)).run(closes, lows, highs, horizon=5)
    assert report.up_signals == report.evaluated
    assert report.hit_rate == 1.0
    assert report.baseline_up_rate == 1.0


def test_상승장에서_항상_DOWN이면_전부_빗나감():
    closes, lows, highs = _series(RISING)
    report = Backtester(predictor=_FixedPredictor(Direction.DOWN)).run(closes, lows, highs, horizon=5)
    assert report.down_signals == report.evaluated
    assert report.hit_rate == 0.0


def test_신호_합계는_평가일수와_일치():
    closes, lows, highs = _series(RISING)
    report = Backtester().run(closes, lows, highs, horizon=5)
    assert report.up_signals + report.down_signals + report.neutral_signals == report.evaluated
    assert report.evaluated == len(closes) - 5 - 51


def test_횡보장은_실제_예측기로_전부_중립():
    closes, lows, highs = _series([100.0] * 100)
    report = Backtester().run(closes, lows, highs, horizon=5)
    assert report.neutral_signals == report.evaluated
    assert report.hit_rate is None


def test_데이터_부족이면_ValueError():
    closes, lows, highs = _series([100.0] * 50)
    with pytest.raises(ValueError):
        Backtester().run(closes, lows, highs, horizon=5)


def test_확률_제시_판정은_표본과_신뢰구간_하한을_모두_요구한다():
    from stock.domain.value_objects.backtest_report import BacktestReport, wilson_lower_bound

    # 표본 부족(n<100): 적중률이 높아도 불인정
    small = BacktestReport(
        horizon_days=5, evaluated=200, up_signals=50, down_signals=0,
        neutral_signals=150, up_hits=45, down_hits=0, baseline_up_rate=0.55,
    )
    assert not small.up_probability_ready

    # 표본 충분 + 하한이 기준선 초과: 인정
    strong = BacktestReport(
        horizon_days=5, evaluated=1000, up_signals=300, down_signals=0,
        neutral_signals=700, up_hits=210, down_hits=0, baseline_up_rate=0.55,
    )
    assert wilson_lower_bound(210, 300) > 0.55
    assert strong.up_probability_ready

    # 표본 충분해도 기준선 언저리: 불인정
    marginal = BacktestReport(
        horizon_days=5, evaluated=1000, up_signals=300, down_signals=0,
        neutral_signals=700, up_hits=168, down_hits=0, baseline_up_rate=0.55,
    )
    assert not marginal.up_probability_ready


def test_리포트_병합은_카운트_합산_기준선은_가중평균():
    from stock.domain.value_objects.backtest_report import BacktestReport

    a = BacktestReport(
        horizon_days=5, evaluated=100, up_signals=10, down_signals=5,
        neutral_signals=85, up_hits=6, down_hits=2, baseline_up_rate=0.6,
    )
    b = BacktestReport(
        horizon_days=5, evaluated=300, up_signals=30, down_signals=15,
        neutral_signals=255, up_hits=18, down_hits=9, baseline_up_rate=0.5,
    )
    m = a.merged(b)
    assert m.evaluated == 400
    assert m.up_signals == 40 and m.down_signals == 20
    assert m.up_hits == 24 and m.down_hits == 11
    assert abs(m.baseline_up_rate - (0.6 * 100 + 0.5 * 300) / 400) < 1e-9


def test_distribution_레짐_분할_합계는_무조건부와_일치():
    closes, lows, highs = _series(RISING)
    # 평가 구간(51~94)을 반씩 다른 레짐으로 — 봉 배열과 같은 길이
    regimes = ["BULL" if i < 70 else "BEAR" for i in range(len(closes))]
    dist = Backtester(predictor=_FixedPredictor(Direction.UP)).distribution(
        closes, lows, highs, horizon=5, regimes=regimes
    )
    total_by_regime = sum(r.evaluated for r in dist.by_regime.values())
    assert total_by_regime == dist.evaluated
    assert set(dist.by_regime) == {"BULL", "BEAR"}
    # 레짐 슬라이스의 방향 표본 합 = 슬라이스 평가일 수
    for stats in dist.by_regime.values():
        assert sum(d.sample_size for d in stats.by_direction.values()) == stats.evaluated
    # 상승장이라 조건부 기준선도 1.0
    assert all(r.baseline_up_rate == 1.0 for r in dist.by_regime.values())


def test_distribution_레짐_None은_무조건부에만_반영():
    closes, lows, highs = _series(RISING)
    regimes: list[str | None] = [None] * len(closes)
    dist = Backtester(predictor=_FixedPredictor(Direction.UP)).distribution(
        closes, lows, highs, horizon=5, regimes=regimes
    )
    assert dist.by_regime == {}
    assert dist.evaluated == len(closes) - 5 - 51


def test_distribution_excluded는_평가에서_빠지고_vetoed로_센다():
    closes, lows, highs = _series(RISING)
    excluded = [False] * len(closes)
    excluded[60] = excluded[61] = True  # 평가 구간 내 2일 veto
    dist = Backtester(predictor=_FixedPredictor(Direction.UP)).distribution(
        closes, lows, highs, horizon=5, excluded=excluded
    )
    assert dist.vetoed == 2
    assert dist.evaluated == len(closes) - 5 - 51 - 2
    assert dist.by_direction["UP"].sample_size == dist.evaluated


def test_distribution_무인자_하위호환():
    closes, lows, highs = _series(RISING)
    dist = Backtester(predictor=_FixedPredictor(Direction.UP)).distribution(
        closes, lows, highs, horizon=5
    )
    assert dist.by_regime == {} and dist.vetoed == 0


def _step_down() -> tuple[list[float], list[float], list[float]]:
    """70봉까지 100, 이후 90으로 계단 하락. 장중 저가=종가로 둬 인위적 낙폭만 남긴다.

    평가 구간(t=51~94, horizon 5)에서:
      t=65~68 → 구간에 90이 들어와 낙폭 + 아직 100 종가도 있어 회복
      t=69    → 구간 전체가 90 — 낙폭 후 미회복
      그 외    → 구간이 한 값으로 평평해 낙폭 없음
    """
    closes = [100.0] * 70 + [90.0] * 30
    return closes, list(closes), list(closes)


def test_distribution_낙폭과_회복을_구간_내에서_수집한다():
    closes, lows, highs = _step_down()
    dist = Backtester(predictor=_FixedPredictor(Direction.NEUTRAL)).distribution(
        closes, lows, highs, horizon=5
    )
    stats = dist.by_direction["NEUTRAL"]
    assert stats.sample_size == len(closes) - 5 - 51  # 44 — 기존 회계 불변

    # 낙폭이 있었던 평가일만 회복률 분모에 들어간다(무조정 구간을 섞으면 회복률이 부풀려진다)
    assert stats.dip_samples == 5           # t=65~69
    assert stats.recovery_rate == 4 / 5     # t=69만 미회복
    assert stats.recovery_days_median == 1.0

    # 최대 낙폭은 장중 저가 기준 -10%
    assert stats.trough_q25_pct is not None
    assert min(stats.trough_q25_pct, stats.trough_median_pct or 0.0) <= 0.0


def test_distribution_무조정_상승은_낙폭_표본이_0():
    closes = [float(100 + i) for i in range(100)]
    dist = Backtester(predictor=_FixedPredictor(Direction.UP)).distribution(
        closes, list(closes), list(closes), horizon=5
    )
    stats = dist.by_direction["UP"]
    assert stats.dip_samples == 0
    assert stats.recovery_rate is None          # 분모가 없으면 비율을 만들지 않는다
    assert stats.recovery_days_median is None
    assert stats.down_close_rate == 0.0
    assert (stats.trough_median_pct or 0.0) > 0.0  # 한 번도 기준가 밑으로 안 내려감


def test_distribution_하락장은_마감_하락률이_1():
    closes = [float(200 - i) for i in range(100)]
    dist = Backtester(predictor=_FixedPredictor(Direction.NEUTRAL)).distribution(
        closes, list(closes), list(closes), horizon=5
    )
    stats = dist.by_direction["NEUTRAL"]
    assert stats.down_close_rate == 1.0
    assert stats.dip_samples == stats.sample_size   # 매일 기준가 아래로 내려감
    assert stats.recovery_rate == 0.0               # 한 번도 회복 못 함


def test_distribution_길이_불일치는_ValueError():
    closes, lows, highs = _series(RISING)
    with pytest.raises(ValueError):
        Backtester().distribution(closes, lows, highs, horizon=5, regimes=["BULL"])
    with pytest.raises(ValueError):
        Backtester().distribution(closes, lows, highs, horizon=5, excluded=[True])
