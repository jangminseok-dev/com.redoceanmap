from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProbabilitySchema(BaseModel):
    """과거 같은 신호의 실측 상승 비율 — 확률 단정이 아니며 표본·신뢰구간을 병기한다."""

    up_rate: float
    sample_size: int
    hits: int
    ci_low: float            # Wilson 95% 하한
    ci_high: float           # Wilson 95% 상한
    baseline_up_rate: float  # 평소(무조건부) 상승 비율
    ready: bool              # n≥100 + Wilson 하한 > 기준선


class BandSchema(BaseModel):
    source: str      # "quantile"(실적 분위수) | "atr"(변동성 콘 폴백)
    q25_pct: float   # horizon일 뒤 수익률 (-0.011 = -1.1%)
    median_pct: float
    q75_pct: float


class ForecastInsightSchema(BaseModel):
    key: str
    tone: str  # positive | neutral | warning
    text: str


class PositionSchema(BaseModel):
    """현재 국면 — 예측이 아니라 "지금까지 얼마나 떨어져 있나"."""

    rsi: float
    rsi_zone: str                  # oversold | neutral | overbought
    drawdown_from_high_pct: float  # 60일 고점 대비 (-0.124 = -12.4%)
    above_support_pct: float       # 60일 저점 대비 여력
    atr_pct: float


class DownsideSchema(BaseModel):
    """하방 리스크 실측 — signal_direction에 DOWN은 오지 않는다(하락 방향 미검증).

    "더 떨어질까"에 단정으로 답하지 않고 같은 신호의 과거 구간 분포로 답한다.
    """

    trough_median_pct: float | None     # 구간 내 장중 최대 낙폭 중앙값
    trough_q25_pct: float | None        # 하위 25% = 더 나쁜 쪽
    down_close_rate: float | None       # horizon 마감이 음수였던 비율
    dip_samples: int                    # 낙폭이 있었던 표본 — 회복률의 분모
    recovery_rate: float | None         # 그중 기준가를 회복한 비율
    recovery_days_median: float | None  # 회복까지 걸린 거래일 중앙값


class StockForecastResponse(BaseModel):
    symbol: str
    resolved_ticker: str
    as_of: datetime
    base_price: float
    horizon_days: int
    signal_direction: str  # UP / DOWN / NEUTRAL (지표 신호 기준, 감성 미반영)
    probability: ProbabilitySchema | None
    band: BandSchema | None
    insights: list[ForecastInsightSchema]
    position: PositionSchema | None = None  # 현재 국면(RSI·낙폭·지지선 여력)
    downside: DownsideSchema | None = None  # 하방·회복 실측 통계
    live: bool = False  # true = 미수집 종목 — yfinance 라이브 이력 기반 계산
    regime: str | None = None         # 현재 시장 레짐(BULL/BEAR/HIGH_VOL)
    regime_conditional: bool = False  # true = 확률·밴드가 현재 레짐 조건부 통계
    earnings_veto: bool = False       # true = 실적 발표 ±2일 관망 강등
