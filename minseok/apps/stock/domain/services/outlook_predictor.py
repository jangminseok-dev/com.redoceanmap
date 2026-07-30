from __future__ import annotations

from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.entities.outlook import Direction, Outlook
from stock.domain.value_objects.indicators import (
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    Indicators,
)
from stock.domain.value_objects.sentiment_score import SentimentScore
from stock.domain.value_objects.signal_breakdown import SignalContribution


class OutlookPredictor:
    """지표 + 뉴스 감성 → 방향 전망. 외부 의존 없는 순수 도메인 서비스.

    결정론적 스코어링만 한다(매매 추천 아님). 종합 점수는 config 가중치로 신호를
    합산해 -1.0 ~ 1.0 로 정규화한 뒤 임계값으로 방향을 판정한다.
    atr_veto가 설정되면 변동성(ATR 비율)이 그보다 클 때 관망(NEUTRAL)한다.
    volume_confirm이 설정되면 거래량(volume_ratio)이 그보다 작을 때 방향 신호를 관망으로 강등한다.
    """

    def breakdown(
        self,
        indicators: Indicators,
        sentiment: SentimentScore,
        config: AnalysisConfig,
    ) -> list[SignalContribution]:
        """신호별 (원값, 가중치, 기여도) 분해 — 가중치 0인 신호도 원값은 노출한다."""
        pairs = (
            ("sentiment", sentiment.value, config.w_sentiment),
            ("rsi", self._rsi_signal(indicators.rsi), config.w_rsi),
            ("trend", self._trend_signal(indicators), config.w_trend),
            ("bollinger", self._bb_signal(indicators.bb_percent_b), config.w_bb),
            ("obv", self._obv_signal(indicators.obv_slope), config.w_obv),
            ("momentum", self._momentum_signal(indicators.momentum_12_1), config.w_momentum),
        )
        return [
            SignalContribution(key=key, signal=signal, weight=weight, contribution=signal * weight)
            for key, signal, weight in pairs
        ]

    @staticmethod
    def score(contributions: list[SignalContribution]) -> float:
        """기여도 합산 → -1.0 ~ 1.0 클램프."""
        return max(-1.0, min(1.0, sum(c.contribution for c in contributions)))

    def predict(
        self,
        indicators: Indicators,
        sentiment: SentimentScore,
        config: AnalysisConfig,
    ) -> Outlook:
        if config.atr_veto is not None and indicators.atr_pct > config.atr_veto:
            return Outlook(direction=Direction.NEUTRAL, confidence=0.0, neutral_reason="atr_veto")

        score = self.score(self.breakdown(indicators, sentiment, config))
        confidence = min(abs(score), 1.0)
        if score >= config.up_threshold:
            return self._confirmed(Direction.UP, confidence, indicators, config)
        if score <= config.down_threshold:
            return self._confirmed(Direction.DOWN, confidence, indicators, config)
        return Outlook(direction=Direction.NEUTRAL, confidence=confidence)

    @staticmethod
    def _confirmed(
        direction: Direction,
        confidence: float,
        indicators: Indicators,
        config: AnalysisConfig,
    ) -> Outlook:
        # 거래량 확인 필터: 평소 대비 거래량이 임계 미만이면 방향 신호를 못 믿고 관망으로 강등
        if config.volume_confirm is not None and indicators.volume_ratio < config.volume_confirm:
            return Outlook(
                direction=Direction.NEUTRAL, confidence=0.0, neutral_reason="volume_confirm"
            )
        return Outlook(direction=direction, confidence=confidence)

    @staticmethod
    def _rsi_signal(rsi: float) -> float:
        # 과매도(30↓)면 반등 기대 +, 과매수(70↑)면 조정 기대 -.
        if rsi <= RSI_OVERSOLD:
            return (RSI_OVERSOLD - rsi) / RSI_OVERSOLD
        if rsi >= RSI_OVERBOUGHT:
            return -(rsi - RSI_OVERBOUGHT) / (100.0 - RSI_OVERBOUGHT)
        return 0.0

    @staticmethod
    def _trend_signal(ind: Indicators) -> float:
        # 정배열(ma20 > ma50) 상승 추세 +, 역배열 -.
        if ind.ma50 <= 0:
            return 0.0
        return max(-1.0, min(1.0, (ind.ma20 - ind.ma50) / ind.ma50 * 10.0))

    @staticmethod
    def _bb_signal(percent_b: float) -> float:
        # 평균회귀: 하단 밴드(%B=0) 근접 +, 상단 밴드(%B=1) 근접 -.
        return max(-1.0, min(1.0, (0.5 - percent_b) * 2.0))

    @staticmethod
    def _obv_signal(obv_slope: float) -> float:
        # 수급 방향 추종: OBV 순증 +, 순감 -. (계산기에서 대체로 -1~1로 정규화됨)
        return max(-1.0, min(1.0, obv_slope))

    @staticmethod
    def _momentum_signal(momentum_12_1: float) -> float:
        # 추세 지속 기대: 12-1 수익률 +25%면 0.5, ±50%에서 포화. (이력 부족 폴백 0.0 = 중립과 일치)
        return max(-1.0, min(1.0, momentum_12_1 * 2.0))
