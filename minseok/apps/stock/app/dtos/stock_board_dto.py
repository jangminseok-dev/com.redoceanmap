from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BoardQuery:
    horizon: int
    limit: int


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


@dataclass(frozen=True)
class BoardView:
    horizon_days: int
    rows: tuple[BoardRowView, ...]
