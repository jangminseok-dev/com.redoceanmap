from __future__ import annotations

from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.entities.outlook import Direction, Outlook
from stock.domain.value_objects.indicators import Indicators
from stock.domain.value_objects.insight_vo import Insight
from stock.domain.value_objects.signal_breakdown import SignalContribution

# 임계값 — chat의 해석 헬퍼(_volatility_text 등)와 동일 기준. 경계 동작은 테스트로 고정한다.
ATR_HIGH = 4.0        # ATR% 이 이상이면 급등락 주의
RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0
TREND_MIN = 0.02      # |ma20-ma50|/ma50 이 이상이면 정/역배열 언급
BB_LOW = 0.2          # %B 하단 부근
BB_HIGH = 0.8         # %B 상단 부근
VOLUME_SURGE = 1.5    # 거래량비 급증
VOLUME_QUIET = 0.7    # 거래량비 한산
MOMENTUM_MIN = 0.15   # |12-1 모멘텀| 언급 기준

_SIGNAL_LABELS = {
    "sentiment": "뉴스 감성",
    "rsi": "RSI",
    "trend": "단기 추세",
    "bollinger": "밴드 위치(볼린저)",
    "obv": "자금 흐름(OBV)",
    "momentum": "1년 추세(모멘텀)",
}


def narrate(
    outlook: Outlook,
    score: float,
    contributions: list[SignalContribution],
    indicators: Indicators,
    config: AnalysisConfig,
    reference_up_signal: bool,
    sentiment_surprise: float | None = None,
) -> list[Insight]:
    """분석 결과 → 초보자용 해석 문장. 두드러진 지표만 골라 서술한다(전부 나열 금지)."""
    insights = [_summary(outlook, score, contributions, indicators, config)]

    if sentiment_surprise is not None and config.w_sentiment > 0:
        insights.append(Insight(
            key="sentiment_surprise", tone="neutral",
            text=(
                "뉴스 감성 신호는 오늘 값 자체가 아니라 최근 30일 평균 대비 변화량으로 "
                f"반영했습니다({sentiment_surprise:+.2f}) — 늘 낙관적인 종목의 상시 긍정을 걸러냅니다."
            ),
        ))
    elif sentiment_surprise is not None:
        # 활성 조합의 감성 가중치가 0 — 판정에 넣지 않는데 "반영했습니다"라고 말하면 거짓이다(2026-09-21)
        insights.append(Insight(
            key="sentiment_surprise", tone="neutral",
            text=(
                f"뉴스 분위기는 최근 30일 평균보다 {sentiment_surprise:+.2f} 달라졌어요 — 참고 정보이고 방향 판정에는 넣지 않습니다"
                "(과거 채점에서 뉴스 분위기는 이후 수익률을 가르지 못했어요)."
            ),
        ))

    if indicators.rsi <= RSI_OVERSOLD:
        insights.append(Insight(
            key="rsi", tone="neutral",
            text=f"RSI {indicators.rsi:.0f} — 최근 많이 내려 과매도 구간입니다(반등 여지).",
        ))
    elif indicators.rsi >= RSI_OVERBOUGHT:
        insights.append(Insight(
            key="rsi", tone="warning",
            text=f"RSI {indicators.rsi:.0f} — 최근 많이 올라 과열 구간입니다(조정 주의).",
        ))

    if indicators.ma50 > 0:
        gap = (indicators.ma20 - indicators.ma50) / indicators.ma50
        if gap >= TREND_MIN:
            insights.append(Insight(
                key="trend", tone="positive",
                text=f"20일 평균이 50일 평균보다 {gap * 100:.1f}% 위(상승 배열) — 단기 추세가 상승 쪽입니다.",
            ))
        elif gap <= -TREND_MIN:
            insights.append(Insight(
                key="trend", tone="warning",
                text=f"20일 평균이 50일 평균보다 {-gap * 100:.1f}% 아래(하락 배열) — 단기 추세가 하락 쪽입니다.",
            ))

    if indicators.bb_percent_b <= BB_LOW:
        insights.append(Insight(
            key="bollinger", tone="neutral",
            text=f"밴드 위치(볼린저 %B) {indicators.bb_percent_b:.2f} — 밴드 하단 부근(단기 과매도권)입니다.",
        ))
    elif indicators.bb_percent_b >= BB_HIGH:
        insights.append(Insight(
            key="bollinger", tone="warning",
            text=f"밴드 위치(볼린저 %B) {indicators.bb_percent_b:.2f} — 밴드 상단 부근(단기 과열권)입니다.",
        ))

    if indicators.volume_ratio >= VOLUME_SURGE or indicators.volume_ratio <= VOLUME_QUIET:
        state = "급증" if indicators.volume_ratio >= VOLUME_SURGE else "한산"
        if indicators.obv_slope > 0:
            flow = "자금 유입 우위(OBV 상승)"
        elif indicators.obv_slope < 0:
            flow = "자금 유출 우위(OBV 하락)"
        else:
            flow = "자금 흐름 중립"
        insights.append(Insight(
            key="volume", tone="neutral",
            text=f"최근 5일 거래량이 20일 평균의 {indicators.volume_ratio:.1f}배로 {state}, {flow}입니다.",
        ))

    if abs(indicators.momentum_12_1) >= MOMENTUM_MIN:
        pct = indicators.momentum_12_1 * 100
        if indicators.momentum_12_1 > 0:
            text = f"1년 추세(12-1 모멘텀) {pct:+.1f}% — 중장기 상승 추세가 뚜렷합니다."
            tone = "positive"
        else:
            text = f"1년 추세(12-1 모멘텀) {pct:+.1f}% — 중장기 하락 추세입니다."
            tone = "warning"
        insights.append(Insight(key="momentum", tone=tone, text=text))

    if indicators.atr_pct * 100 >= ATR_HIGH:
        insights.append(Insight(
            key="volatility", tone="warning",
            text=f"하루 변동폭이 큰 편(ATR {indicators.atr_pct * 100:.1f}%) — 급등락에 주의하세요.",
        ))

    if reference_up_signal:
        insights.append(Insight(
            key="reference", tone="neutral",
            text="'과매도+밴드 하단' 참고 조건에 해당합니다 — 통계적으로 검증된 신호가 아니며 "
                 "상승 확률이나 매수 근거는 아닙니다.",
        ))
    return insights


def _summary(
    outlook: Outlook,
    score: float,
    contributions: list[SignalContribution],
    indicators: Indicators,
    config: AnalysisConfig,
) -> Insight:
    if outlook.direction is Direction.NEUTRAL:
        if outlook.neutral_reason == "atr_veto":
            return Insight(
                key="summary", tone="warning",
                text=f"변동성이 너무 커서(ATR {indicators.atr_pct * 100:.1f}%) 방향 판단을 쉬는 관망 판정입니다.",
            )
        if outlook.neutral_reason == "volume_confirm":
            return Insight(
                key="summary", tone="neutral",
                text=f"방향 신호는 있었지만 거래량이 평소의 {indicators.volume_ratio:.1f}배로 적어 "
                     "관망으로 낮췄습니다.",
            )
        return Insight(
            key="summary", tone="neutral",
            text=f"지표 신호 합계 {score:+.2f}가 기준(±{config.up_threshold:.2f})에 못 미쳐 "
                 "중립(관망) 판정입니다.",
        )

    top = max(contributions, key=lambda c: abs(c.contribution))
    is_up = outlook.direction is Direction.UP
    threshold = config.up_threshold if is_up else config.down_threshold
    return Insight(
        key="summary",
        tone="positive" if is_up else "warning",
        text=f"종합 점수 {score:+.2f}(기준 {threshold:+.2f}) — "
             f"{_SIGNAL_LABELS[top.key]}({top.contribution:+.2f})이 가장 큰 "
             f"{'상승' if is_up else '하락'} 기여입니다.",
    )
