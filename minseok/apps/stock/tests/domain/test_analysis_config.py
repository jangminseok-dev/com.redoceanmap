"""forecast_signal() 조합 회귀 — 이 조합이 깨지면 예측 스냅샷이 조용히 전량 NEUTRAL로 돌아간다."""

from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.entities.outlook import Direction
from stock.domain.services.outlook_predictor import OutlookPredictor
from stock.domain.value_objects.indicators import Indicators
from stock.domain.value_objects.sentiment_score import SentimentScore

NEUTRAL = SentimentScore(0.0)


def _ind(
    rsi: float = 50.0,
    bb: float = 0.5,
    momentum: float = 0.0,
    ma20: float = 100.0,
    ma50: float = 100.0,
) -> Indicators:
    return Indicators(
        rsi=rsi, ma20=ma20, ma50=ma50, support=90.0, resistance=110.0,
        bb_percent_b=bb, momentum_12_1=momentum,
    )


def test_forecast_signal_does_not_use_sentiment():
    """감성 중립 경로 전용 — 감성 가중치가 0이어야 사장되는 예산이 없다."""
    config = AnalysisConfig.forecast_signal()
    assert config.w_sentiment == 0.0
    assert config.w_rsi + config.w_bb + config.w_momentum == 1.0


def test_forecast_signal_never_predicts_down():
    """하락은 검증되지 않았다 — 어떤 지표 조합에서도 DOWN이 나오면 안 된다(임계값 도달 불가)."""
    predictor = OutlookPredictor()
    config = AnalysisConfig.forecast_signal()
    # 모든 신호를 최대 음수로 밀어도(과매수 + 밴드 상단 + 모멘텀 -50%) score는 -1.0에서 멈춘다
    worst = _ind(rsi=100.0, bb=1.0, momentum=-1.0)
    assert predictor.score(predictor.breakdown(worst, NEUTRAL, config)) <= -1.0 + 1e-9
    assert predictor.predict(worst, NEUTRAL, config).direction is Direction.NEUTRAL


def test_forecast_signal_reaches_up_on_oversold_reversal():
    """과매도 + 밴드 하단이면 UP이 나온다 — default()로는 산술적으로 불가능했던 지점."""
    predictor = OutlookPredictor()
    oversold = _ind(rsi=20.0, bb=0.0)  # rsi 0.333×0.4 + bb 1.0×0.4 = 0.533 ≥ 0.35
    out = predictor.predict(oversold, NEUTRAL, AnalysisConfig.forecast_signal())
    assert out.direction is Direction.UP


def test_default_config_cannot_reach_threshold_without_sentiment():
    """왜 조합을 바꿨는지 고정 — default()는 감성 없이는 UP도 DOWN도 낼 수 없다."""
    predictor = OutlookPredictor()
    config = AnalysisConfig.default()
    # 추세를 포화시키고 RSI까지 극단으로 밀어도 감성 0이면 상한이 0.5 — 그런데 실측 대부분은
    # RSI 신호 0(30~70 구간)이라 추세 기여 0.2가 천장이다.
    trend_only = _ind(rsi=50.0, ma20=200.0, ma50=100.0)
    score = predictor.score(predictor.breakdown(trend_only, NEUTRAL, config))
    assert abs(score) <= 0.2 + 1e-9
    assert score < config.up_threshold
    assert predictor.predict(trend_only, NEUTRAL, config).direction is Direction.NEUTRAL
