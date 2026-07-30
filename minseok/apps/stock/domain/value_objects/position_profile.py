from __future__ import annotations

from dataclasses import dataclass

from stock.domain.value_objects.indicators import (
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    Indicators,
)

OVERSOLD = "oversold"
NEUTRAL = "neutral"
OVERBOUGHT = "overbought"


@dataclass(frozen=True, slots=True)
class PositionProfile:
    """"지금 어느 국면에 있나" — 이미 계산된 지표에서 파생한 현재 위치. 새 지표 계산은 없다.

    방향 전망(`Outlook`)이 "앞으로"를 말한다면 이쪽은 "지금까지"를 말한다 —
    얼마나 떨어져 있고, 저점까지 여력이 얼마고, RSI가 어느 구간인지.
    판정에는 개입하지 않는 서술용 값이다(가중치·임계값과 무관).
    """

    rsi: float
    rsi_zone: str                  # oversold | neutral | overbought (경계는 신호 계산과 공유)
    drawdown_from_high_pct: float  # 최근 고점(저항선) 대비 (-0.124 = -12.4%)
    above_support_pct: float       # 최근 저점(지지선) 대비 여력 (+0.031 = +3.1%)
    atr_pct: float                 # 일 변동성 — 낙폭이 "평소 범위"인지 가늠하는 척도

    @classmethod
    def from_indicators(cls, ind: Indicators, base_price: float) -> "PositionProfile":
        return cls(
            rsi=ind.rsi,
            rsi_zone=_zone(ind.rsi),
            # 지지/저항은 최근 60거래일 저점·고점(IndicatorCalculator). 0 이하 방어는
            # 실데이터에선 불필요하지만 합성·열화 입력에서 ZeroDivision을 막는다.
            drawdown_from_high_pct=(
                base_price / ind.resistance - 1.0 if ind.resistance > 0 else 0.0
            ),
            above_support_pct=base_price / ind.support - 1.0 if ind.support > 0 else 0.0,
            atr_pct=ind.atr_pct,
        )


def _zone(rsi: float) -> str:
    if rsi <= RSI_OVERSOLD:
        return OVERSOLD
    if rsi >= RSI_OVERBOUGHT:
        return OVERBOUGHT
    return NEUTRAL
