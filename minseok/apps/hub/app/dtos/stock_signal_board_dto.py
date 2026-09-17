"""신호 보드 계약 DTO — 워치리스트 전체의 최신 방향 신호 목록.

허브가 공개하는 앱 간 협력 계약. stock(스포크)이 보드 유스케이스(stock_board)로 채우고
chat(스포크)이 "상승 신호 나온 종목 뭐야?" 류 조회 질문에 소비한다(4차 실측 S8 t4 —
신호 조회 라우팅이 없어 뉴스로 답했다). 원시 수치만 담는다 — 문장화는 소비자 몫.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StockSignalRow:
    ticker: str
    name: str                      # 표시용 한글명 — 모르는 티커는 티커 그대로
    as_of: datetime                # 신호 기준일(스냅샷)
    direction: str                 # UP | DOWN | NEUTRAL
    price: float                   # 최신 수집 종가 — 준실시간 아님
    change_pct: float | None       # 전일 대비(0.02 = +2%)
    up_rate: float | None          # 같은 신호일 때 **그 방향**으로 간 과거 비율(표본 없으면 None)
    baseline_up_rate: float | None
    ready: bool                    # 통계적 유의(Wilson 하한 > 기준선)
    rsi: float | None = None       # 신호 근거(역추세 — 과매도일수록 상승 쪽 신호)
    bb_percent_b: float | None = None
    signal_days: int = 1           # 같은 방향 신호 연속 일수
    since_signal_pct: float | None = None  # 연속 신호 첫날 대비 최신가 등락
    # 위험 신호(2026-09-17 재설계) — 판정 불가면 None
    rv20: float | None = None
    rv_percentile: float | None = None
    vol_state: str | None = None       # HIGH | NORMAL | LOW
    trend: str | None = None           # UP | DOWN | MIXED
    drawdown_risk: str | None = None   # HIGH | NORMAL | LOW


@dataclass(frozen=True)
class RiskSignalStat:
    """위험 신호 상태 하나의 검증 실측(검증 구간) — 수치 인용은 validated일 때만."""

    key: str
    label: str
    outcome_label: str
    side: str
    test_rate: float | None
    base_rate: float | None
    lift: float | None
    n_eff: float
    validated: bool


@dataclass(frozen=True)
class StockSignalBoardInfo:
    horizon_days: int
    rows: tuple[StockSignalRow, ...]  # 보드 정렬 그대로(위험 신호 순)
    risk_stats: tuple[RiskSignalStat, ...] = ()
    risk_test_period: str | None = None
