"""forecast_narrator 서사 — 하방·회복·국면 문장이 열화 입력에서도 깨지지 않아야 한다."""

from stock.domain.services import forecast_narrator
from stock.domain.value_objects.forecast_distribution import DirectionStats
from stock.domain.value_objects.indicators import Indicators
from stock.domain.value_objects.position_profile import PositionProfile


def _stats(**kwargs) -> DirectionStats:
    base = dict(sample_size=200, hits=110, q25=-0.02, median=0.005, q75=0.03)
    return DirectionStats(**{**base, **kwargs})


def _position(rsi: float = 28.0) -> PositionProfile:
    return PositionProfile.from_indicators(
        Indicators(
            rsi=rsi, ma20=100.0, ma50=105.0, support=90.0, resistance=120.0, atr_pct=0.02
        ),
        base_price=100.0,
    )


def _keys(insights) -> set[str]:
    return {i.key for i in insights}


def test_국면_하방_회복_문장이_모두_나온다():
    stats = _stats(
        trough_median_pct=-0.032, trough_q25_pct=-0.068, down_close_rate=0.41,
        dip_samples=150, recovery_rate=0.59, recovery_days_median=3.0,
    )
    insights = forecast_narrator.narrate(
        "UP", stats, baseline_up_rate=0.52, horizon_days=5, ready=True, position=_position()
    )
    assert {"position", "downside", "recovery"} <= _keys(insights)

    position = next(i for i in insights if i.key == "position")
    assert "고점 대비 -16.7%" in position.text   # 120 → 100
    assert "저점보다 +11.1%" in position.text     # 90 → 100
    assert "과매도 구간" in position.text
    assert "하루 평균 변동폭(2.0%)의 8배" in position.text  # 16.7 / 2.0

    downside = next(i for i in insights if i.key == "downside")
    assert "중앙값 -3.2%" in downside.text and "나쁜 쪽 25%는 -6.8%" in downside.text
    assert "하락 마감은 41%" in downside.text

    recovery = next(i for i in insights if i.key == "recovery")
    assert "150회 중 59%" in recovery.text and "중앙값 3거래일" in recovery.text


def test_낙폭_사례가_없으면_회복률을_만들지_않는다():
    stats = _stats(
        trough_median_pct=0.004, trough_q25_pct=0.001, down_close_rate=0.0,
        dip_samples=0, recovery_rate=None, recovery_days_median=None,
    )
    insights = forecast_narrator.narrate(
        "UP", stats, baseline_up_rate=0.52, horizon_days=5, ready=True, position=_position(rsi=55.0)
    )
    recovery = next(i for i in insights if i.key == "recovery")
    assert "기준가 아래로 내려간 사례가 없었습니다" in recovery.text
    assert "%가" not in recovery.text  # 분모 없는 비율을 만들지 않는다


def test_position_미주입_표본0이면_해당_문장을_생략한다():
    insights = forecast_narrator.narrate(
        "NEUTRAL",
        DirectionStats(sample_size=0, hits=0, q25=None, median=None, q75=None),
        baseline_up_rate=0.5, horizon_days=5, ready=False,
    )
    assert "position" not in _keys(insights)
    assert "downside" not in _keys(insights)
    assert "basis" in _keys(insights)  # 근거 고지는 항상 남는다


def test_근거_고지에_하락_미예측을_밝힌다():
    insights = forecast_narrator.narrate(
        "UP", _stats(), baseline_up_rate=0.5, horizon_days=5, ready=True
    )
    basis = next(i for i in insights if i.key == "basis")
    assert "뉴스 감성은 반영되지 않습니다" in basis.text
    assert "하락 방향은 검증된 신호가 없어 예측하지 않고" in basis.text
