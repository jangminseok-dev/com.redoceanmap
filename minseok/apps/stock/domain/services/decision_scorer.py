"""판단 사후 채점 — 진입 주문(BUY·SHORT)마다 5거래일 실현 수익률로 적중을 매긴다.

적중 정의는 스냅샷 채점과 같다(`hit_unit`·`is_up_hit`·`is_down_hit`, 변동성 초과).
숏은 부호를 뒤집어 본다. 청산 주문(SELL·COVER)은 채점하지 않는다 — 방향 판단이 아니다.
"""
from __future__ import annotations

from dataclasses import dataclass

from stock.domain.value_objects.backtest_report import hit_unit, is_down_hit, is_up_hit

SCORE_HORIZON_SESSIONS = 5


@dataclass(frozen=True)
class OrderScore:
    ticker: str
    action: str
    reason_kind: str
    realized_return_pct: float  # 진입가 대비, 롱 기준 부호(숏도 그대로 저장 — hit이 방향을 안다)
    hit: bool


def score_entry(
    *, action: str, reason_kind: str, ticker: str, entry_price: float, exit_close: float,
    atr_pct: float | None,
) -> OrderScore:
    ret = exit_close / entry_price - 1.0
    unit = hit_unit(atr_pct, SCORE_HORIZON_SESSIONS)
    hit = is_up_hit(ret, unit) if action == "BUY" else is_down_hit(ret, unit)
    return OrderScore(ticker, action, reason_kind, round(ret, 6), hit)
