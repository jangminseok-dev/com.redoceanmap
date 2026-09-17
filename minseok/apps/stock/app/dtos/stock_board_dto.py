from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BoardQuery:
    horizon: int
    limit: int
    # risk = 위험 신호 순(2026-09-17 재설계, 화면·채팅 기본) · signal = 방향 신호 세기 순(기존)
    order: str = "signal"


@dataclass(frozen=True)
class BoardSignalRow:
    """리포지토리가 돌려주는 원자료 한 줄 — 최신 스냅샷 + 최근 종가."""

    ticker: str
    as_of: datetime
    direction: str  # UP | DOWN | NEUTRAL
    score: float
    base_price: float
    up_rate: float | None
    baseline_up_rate: float | None
    ready: bool
    closes: tuple[float, ...]  # 스파크라인용 최근 종가(과거 → 최신)
    price_as_of: datetime | None  # closes[-1]이 속한 세션일 — as_of(신호 기준일)와 다를 수 있다
    # 마지막 봉의 거래량. 봉이 없으면 None(수집 전 종목) — 기본값을 둬 기존 호출부를 깨지 않는다
    volume: int | None = None
    # 신호 근거·연속성(2026-09-17) — "상승 신호인데 떨어지는 중"으로 읽히던 역추세 신호를 설명한다
    rsi: float | None = None
    bb_percent_b: float | None = None
    signal_days: int = 1                 # 같은 방향 스냅샷이 끊기지 않고 이어진 일수(오늘 포함)
    signal_start_price: float | None = None  # 그 연속 구간 첫 스냅샷의 기준가


@dataclass(frozen=True)
class BoardRowView:
    ticker: str
    name: str  # 표시용 한글명 — 없으면 티커 그대로
    as_of: datetime
    direction: str
    score: float
    price: float  # 최신 종가(수집분 기준 — 준실시간 아님)
    change_pct: float | None  # 전일 대비
    up_rate: float | None
    baseline_up_rate: float | None
    edge_pct: float | None  # up_rate − baseline (0.02 = +2%p). 둘 중 하나라도 없으면 None
    ready: bool
    sparkline: tuple[float, ...]
    price_as_of: datetime | None  # 가격 기준일. 신호 기준일(as_of)보다 최신일 수 있다
    volume: int | None  # 마지막 봉 거래량(주)
    # 거래대금 = 종가 × 거래량. **통화가 섞인다** — 워치리스트 대부분이 미국 종목이라
    # 달러와 원이 한 컬럼에 온다. 그래서 이 값으로 정렬하지 않는다(보드 정렬은 신호 세기 순).
    turnover: float | None
    rsi: float | None = None
    bb_percent_b: float | None = None
    signal_days: int = 1
    since_signal_pct: float | None = None  # 연속 신호 첫날 기준가 대비 최신가(0.03 = +3%)
    # 위험 신호(2026-09-17) — 봉이 모자라면 전부 None
    rv20: float | None = None              # 최근 20일 실현 변동성(연율)
    rv_percentile: float | None = None     # 자기 1년 분포 안 위치(0~1)
    vol_state: str | None = None           # HIGH | NORMAL | LOW
    trend: str | None = None               # UP | DOWN | MIXED
    drawdown_risk: str | None = None       # HIGH | NORMAL | LOW


@dataclass(frozen=True)
class RiskStatView:
    """위험 신호 한 상태의 검증 실측 — 최신 주간 리포트의 검증 구간(2021~) 값."""

    key: str                    # vol_high | vol_low | drop_high | drop_low
    label: str
    outcome_label: str
    side: str                   # high(기준보다 잦음) | low(드묾)
    test_rate: float | None
    base_rate: float | None
    lift: float | None
    n_eff: float
    train_lift: float | None
    validated: bool             # 학습·검증 두 구간 모두 95% 구간이 기준률과 갈라짐


@dataclass(frozen=True)
class BoardView:
    horizon_days: int
    rows: tuple[BoardRowView, ...]
    risk_stats: tuple[RiskStatView, ...] = ()
    risk_report_ran_at: datetime | None = None
    risk_test_period: str | None = None    # "2021-01~2026-09"
