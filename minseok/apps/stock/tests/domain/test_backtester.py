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


def test_리포트_병합은_카운트_합산_기준선은_신호수_가중():
    from stock.domain.value_objects.backtest_report import BacktestReport

    # 평가일은 b가 3배 길지만 신호는 a가 3배 많다 — 두 가중이 서로 다른 답을 내는 표본이라야
    # "신호 수 가중"이 실제로 걸렸는지 구분된다(평가일 가중이면 0.525). 가중치는 **그 방향의**
    # 신호 수다(UP 기준선은 up_signals로) — 상승·하락 기준선이 별개 축이라 함께 섞지 않는다.
    a = BacktestReport(
        horizon_days=5, evaluated=100, up_signals=25, down_signals=5,
        neutral_signals=70, up_hits=15, down_hits=2, baseline_up_rate=0.6,
    )
    b = BacktestReport(
        horizon_days=5, evaluated=300, up_signals=8, down_signals=2,
        neutral_signals=290, up_hits=4, down_hits=1, baseline_up_rate=0.5,
    )
    m = a.merged(b)
    assert m.evaluated == 400
    assert m.up_signals == 33 and m.down_signals == 7
    assert m.up_hits == 19 and m.down_hits == 3
    assert abs(m.baseline_up_rate - (0.6 * 25 + 0.5 * 8) / 33) < 1e-9


def test_병합_하락기준선은_하락신호_수로_가중하고_모르면_None():
    from stock.domain.value_objects.backtest_report import BacktestReport

    a = BacktestReport(
        horizon_days=5, evaluated=100, up_signals=25, down_signals=30,
        neutral_signals=45, up_hits=15, down_hits=12, baseline_up_rate=0.6,
        baseline_down_rate=0.30,
    )
    b = BacktestReport(
        horizon_days=5, evaluated=300, up_signals=8, down_signals=10,
        neutral_signals=282, up_hits=4, down_hits=3, baseline_up_rate=0.5,
        baseline_down_rate=0.20,
    )
    assert abs(a.merged(b).baseline_down_rate - (0.30 * 30 + 0.20 * 10) / 40) < 1e-9

    # 한쪽이라도 하락 기준선을 모르면 합칠 수 없다 — 없는 기준선을 지어내지 않는다
    unknown = BacktestReport(
        horizon_days=5, evaluated=100, up_signals=1, down_signals=1,
        neutral_signals=98, up_hits=1, down_hits=1, baseline_up_rate=0.5,
    )
    assert a.merged(unknown).baseline_down_rate is None


def test_하락_기준선을_모르면_확률_판정을_하지_않는다():
    from stock.domain.value_objects.backtest_report import BacktestReport

    strong = dict(
        horizon_days=5, evaluated=1000, up_signals=0, down_signals=200,
        neutral_signals=800, up_hits=0, down_hits=140, baseline_up_rate=0.4,
    )
    assert BacktestReport(**strong).down_probability_ready is False          # 기준선 미상
    assert BacktestReport(**strong, baseline_down_rate=0.30).down_probability_ready is True
    # (1 − 상승기준선)=0.6과 겨루던 옛 규칙이었다면 하한 63%가 못 이겨 False였을 자리다


def test_병합_신호가_한쪽도_없으면_기준선은_평가일_가중으로_되돌린다():
    from stock.domain.value_objects.backtest_report import BacktestReport

    a = BacktestReport(
        horizon_days=5, evaluated=100, up_signals=0, down_signals=0,
        neutral_signals=100, up_hits=0, down_hits=0, baseline_up_rate=0.6,
    )
    b = BacktestReport(
        horizon_days=5, evaluated=300, up_signals=0, down_signals=0,
        neutral_signals=300, up_hits=0, down_hits=0, baseline_up_rate=0.5,
    )
    assert abs(a.merged(b).baseline_up_rate - (0.6 * 100 + 0.5 * 300) / 400) < 1e-9


def test_적중은_변동성_문턱을_넘어야_한다():
    """계속 오르지만 상승폭이 잡음보다 작으면 적중이 아니다 — 부호 판정과 갈리는 지점."""
    # 하루 +0.01(5일 ≈ +0.05%)인데 일중 폭은 ±2(ATR ≈ 4%) — 문턱은 4%×√5×0.25 ≈ 2.2%
    closes = [100.0 + 0.01 * i for i in range(100)]
    lows = [c - 2.0 for c in closes]
    highs = [c + 2.0 for c in closes]
    report = Backtester(predictor=_FixedPredictor(Direction.UP)).run(
        closes, lows, highs, horizon=5,
    )
    assert report.up_signals == report.evaluated
    assert report.up_hits == 0          # 전 구간 상승인데도 적중 0
    assert report.baseline_up_rate == 0.0  # 기준선도 같은 규칙으로 세므로 함께 0


def test_적중_문턱은_변동성에_비례한다():
    """같은 상승폭이라도 잡음이 작은 종목에서는 적중이다 — 위 테스트의 대조군."""
    closes = [100.0 + 0.01 * i for i in range(100)]
    lows = [c - 0.002 for c in closes]
    highs = [c + 0.002 for c in closes]
    report = Backtester(predictor=_FixedPredictor(Direction.UP)).run(
        closes, lows, highs, horizon=5,
    )
    assert report.up_hits == report.up_signals
    assert report.baseline_up_rate == 1.0


def test_ATR을_모르면_부호_판정으로_열화한다():
    from stock.domain.value_objects.backtest_report import hit_unit, is_up_hit

    assert hit_unit(None, 5) == 0.0
    assert is_up_hit(0.0001, hit_unit(None, 5)) is True
    assert is_up_hit(-0.0001, hit_unit(None, 5)) is False


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
