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


def test_하락은_어떤_과매수에도_발화하지_않는다():
    """2026-09-17 하락 무발화 복귀 — 81종목 10년 재검증의 뒤 5년에서 기준선 미달(-1.0%p, 신호 뒤 5일 +0.38%).

    8/28에 16종목으로 검증했던 -0.45가 넓은 워치리스트에서 유지되지 않았다. 점수는 [-1, 1]로
    클램프되므로 -1.01은 도달 불가 — 가장 강한 과매수(-1.0)도 관망이다.
    """
    predictor = OutlookPredictor()
    for config in (AnalysisConfig.forecast_signal(), AnalysisConfig.default()):
        assert config.down_threshold < -1.0
        extreme = _ind(rsi=100.0, bb=1.5, momentum=-1.0)
        assert predictor.predict(extreme, NEUTRAL, config).direction is Direction.NEUTRAL


def test_forecast_signal_reaches_up_on_oversold_reversal():
    """과매도 + 밴드 하단이면 UP이 나온다 — default()로는 산술적으로 불가능했던 지점."""
    predictor = OutlookPredictor()
    oversold = _ind(rsi=20.0, bb=0.0)  # rsi 0.333×0.4 + bb 1.0×0.4 = 0.533 ≥ 0.35
    out = predictor.predict(oversold, NEUTRAL, AnalysisConfig.forecast_signal())
    assert out.direction is Direction.UP


def test_default_matches_forecast_signal_when_sentiment_neutral():
    """감성이 0이면 default()의 UP 판정이 검증 조합(forecast_signal)과 완전히 같다.

    **이 등가가 뉴스 비중 0.5→0.2 조정의 유일한 근거다.** default()는 검증 조합에 일괄 0.8을
    곱한 값이고 스코어가 선형 가중합이라 임계 비교 결과가 보존된다. 이게 깨지면 analyze 경로가
    백테스트로 검증된 적 없는 조합으로 방향을 판정하게 된다.

    DOWN은 비교하지 않는다 — 두 조합의 하락 임계가 -0.45와 -0.36(0.8배)으로 스케일만 다르고
    default는 북마크 알림 상태를 위해 DOWN을 낸다.
    """
    predictor = OutlookPredictor()
    default = AnalysisConfig.default()
    verified = AnalysisConfig.forecast_signal()

    cases = [
        _ind(rsi=r, bb=b, momentum=m)
        for r in (10.0, 25.0, 50.0, 75.0, 95.0)
        for b in (0.0, 0.3, 0.5, 0.8, 1.0)
        for m in (-0.6, 0.0, 0.6)
    ]
    for ind in cases:
        up_default = predictor.predict(ind, NEUTRAL, default).direction is Direction.UP
        up_verified = predictor.predict(ind, NEUTRAL, verified).direction is Direction.UP
        assert up_default == up_verified, f"UP 판정이 갈렸다: {ind}"


def test_default_sentiment_alone_cannot_decide_direction():
    """뉴스만으로는 방향이 나오지 않는다 — 감성은 판정을 뒤집는 축이 아니라 보정항이다.

    감성 가중치 0.2 < 임계 0.28이므로, 지표가 전부 중립이면 감성이 최대(±1.0)여도 NEUTRAL이다.
    "뉴스 비중을 낮춘다"는 요구가 실제로 코드에서 성립하는지를 이 테스트가 고정한다.
    """
    predictor = OutlookPredictor()
    config = AnalysisConfig.default()
    flat = _ind(rsi=50.0, bb=0.5, momentum=0.0)  # 모든 지표 신호 0

    for sentiment in (SentimentScore(1.0), SentimentScore(-1.0)):
        score = predictor.score(predictor.breakdown(flat, sentiment, config))
        assert abs(score) <= config.w_sentiment + 1e-9
        assert abs(score) < config.up_threshold
        assert predictor.predict(flat, sentiment, config).direction is Direction.NEUTRAL
