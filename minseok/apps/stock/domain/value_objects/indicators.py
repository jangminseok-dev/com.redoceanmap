from __future__ import annotations

from dataclasses import dataclass

# RSI 국면 경계 — 신호 계산(OutlookPredictor._rsi_signal)과 국면 라벨(PositionProfile)이
# 같은 값을 봐야 한다. 둘이 갈라지면 "과매도인데 신호는 0" 같은 모순이 화면에 뜬다.
RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0


@dataclass(frozen=True, slots=True)
class Indicators:
    """트레이더가 보는 기술적 지표 묶음(특정 종목·시점). 외부 의존 없는 순수 값."""

    rsi: float           # 0~100, 30↓ 과매도 / 70↑ 과매수
    ma20: float          # 20일 이동평균
    ma50: float          # 50일 이동평균
    support: float       # 최근 지지선(저점)
    resistance: float    # 최근 저항선(고점)
    atr_pct: float = 0.0        # ATR(14)/종가 — 변동성 비율 (0.02 = 일 2%)
    bb_percent_b: float = 0.5   # 볼린저 %B (0=하단 밴드, 1=상단 밴드, 범위 밖 가능)
    volume_ratio: float = 1.0   # 최근 5일 평균 거래량 / 최근 20일 평균 (1.0 = 평소 수준)
    obv_slope: float = 0.0      # OBV 20일 변화 / 20일 평균 거래량 — 수급 방향(-∞~∞, 대체로 ±수 단위)
    momentum_12_1: float = 0.0  # 12-1 모멘텀: 12개월 전 → 1개월 전 수익률 (이력 253봉 미만이면 중립 0.0)

    def __post_init__(self) -> None:
        if not 0.0 <= self.rsi <= 100.0:
            raise ValueError("RSI는 0~100 범위여야 합니다.")
