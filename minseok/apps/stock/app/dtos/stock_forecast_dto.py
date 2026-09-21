from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from stock.domain.value_objects.insight_vo import Insight
from stock.domain.value_objects.position_profile import PositionProfile


@dataclass(frozen=True)
class ForecastQuery:
    """확률·예측 밴드 조회 입력 — 저장 일봉(DB) 기반, 지표 신호 기준(감성 미반영)."""

    symbol: str
    horizon: int = 5  # 전망 평가 구간(거래일)


@dataclass(frozen=True)
class ProbabilityInfo:
    """'지금과 같은 방향 신호' 조건부의 과거 상승 비율 — 확률 단정이 아니라 실측 통계."""

    up_rate: float          # hits / sample_size
    sample_size: int
    hits: int
    ci_low: float           # Wilson 95% 하한
    ci_high: float          # Wilson 95% 상한
    baseline_up_rate: float  # 항상-UP 기준선
    ready: bool             # n≥100 + Wilson 하한 > 기준선 (확률 제시 판정 기준)


@dataclass(frozen=True)
class BandInfo:
    """예측 범위 — quantile(실적 분위수) 또는 atr(변동성 콘 폴백)."""

    source: str      # "quantile" | "atr"
    q25_pct: float   # horizon일 뒤 수익률 (-0.011 = -1.1%)
    median_pct: float
    q75_pct: float


@dataclass(frozen=True)
class DownsideInfo:
    """하방 리스크 — 같은 신호가 났던 과거 구간에서 얼마나 빠졌고 얼마나 회복했나.

    하락 **방향 예측**은 검증되지 않았으므로(재채점 2·3차 모두 두 구간 연속 통과 실패)
    "떨어진다"고 단정하지 않고 실측 분포만 제시한다. `signal_direction`에 DOWN은 오지 않는다.
    """

    trough_median_pct: float | None      # 구간 내 장중 최대 낙폭 중앙값
    trough_q25_pct: float | None         # 하위 25% = 더 나쁜 쪽
    down_close_rate: float | None        # horizon 마감이 음수였던 비율
    dip_samples: int                     # 낙폭이 있었던 표본 — 회복률의 분모
    recovery_rate: float | None          # 그중 기준가를 회복한 비율
    recovery_days_median: float | None   # 회복까지 걸린 거래일 중앙값


@dataclass(frozen=True)
class RiskEvidence:
    """지금 상태의 검증 실측 — 학습·검증 두 구간 모두 통과(validated)한 것만 싣는다."""

    key: str            # vol_high | vol_low | drop_high | drop_low
    test_rate: float    # 검증 구간에서 그 결과가 나온 비율
    base_rate: float    # 평소(무조건부) 비율


@dataclass(frozen=True)
class RiskInfo:
    """위험 신호 — 신호 보드와 같은 판정(risk_signal.state_at). 방향과 달리 검증 구간에서도 유지된 축."""

    vol_state: str          # HIGH | NORMAL | LOW — 향후 20거래일 변동성 확대 가능성
    drawdown_risk: str      # HIGH | NORMAL | LOW — 20거래일 안 -10% 하락 가능성
    trend: str              # UP | DOWN | MIXED
    rv20: float             # 최근 20일 실현 변동성(연율)
    rv_percentile: float    # 자기 1년 분포 안 위치(0~1)
    evidence: tuple[RiskEvidence, ...] = ()


@dataclass(frozen=True)
class StockForecastView:
    symbol: str
    resolved_ticker: str
    as_of: datetime          # 마지막 봉 시각
    base_price: float        # 마지막 종가 — 밴드의 기준점
    horizon_days: int
    signal_direction: str    # UP / DOWN / NEUTRAL (지표 신호 기준)
    probability: ProbabilityInfo | None  # 표본 0이면 None
    band: BandInfo | None                # 분위수·ATR 모두 불가하면 None
    insights: list[Insight]
    # 현재 국면(RSI·고점 대비 낙폭) — Insight와 같이 도메인 VO를 그대로 실어보낸다
    position: PositionProfile | None = None
    downside: DownsideInfo | None = None  # 하방·회복 실측 통계 — 표본 0이면 None
    risk: RiskInfo | None = None          # 위험 신호 — 봉이 모자라면 None
    live: bool = False       # True = 미수집 종목 — yfinance 라이브 이력 기반 계산
    regime: str | None = None        # 현재 시장 레짐(BULL/BEAR/HIGH_VOL) — 지수 미수집이면 None
    regime_conditional: bool = False  # True = 확률·밴드가 현재 레짐 조건부 통계
    earnings_veto: bool = False       # True = 실적 발표 ±2일 — 방향을 관망으로 강등
