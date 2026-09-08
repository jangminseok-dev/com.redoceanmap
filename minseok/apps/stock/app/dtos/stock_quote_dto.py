from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteQuery:
    symbol: str


@dataclass(frozen=True)
class QuoteView:
    """준실시간 현재가 — yfinance 무료 시세라 지연(약 15~20분)이 있다."""

    symbol: str
    price: float
    delayed: bool  # 항상 True(yfinance) — 실시간 벤더로 교체 시 False 가능
    previous_close: float | None = None  # 전일 종가 — 벤더가 못 주면 None
    change_pct: float | None = None  # 전일 대비 등락률 (0.012 = +1.2%)
    fetched_at: str | None = None  # 벤더 조회 시각(UTC ISO) — 지연 시세가 언제 기준인지(2026-09-08 QA P05)
