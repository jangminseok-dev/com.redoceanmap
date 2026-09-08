"""모의투자 원장 — 체결·청산·평가의 산술. 순수 함수, 누가 결정했는지 모른다.

롱: BUY로 열고 SELL로 닫는다. 숏: SHORT로 열고 COVER로 닫는다(레버리지 없음).
숏은 명목가를 현금에서 빼 담보로 묶는다 — 그래서 숏 포지션의 평가액은
`(2×진입가 − 현재가) × 수량`이다(담보 회수 + 미실현 손익). 자산 = 현금 + 포지션 평가액.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from stock.domain.services import paper_rules as rules


@dataclass(frozen=True)
class Position:
    ticker: str
    side: str  # LONG | SHORT
    quantity: int
    avg_price: float  # 종목 통화 기준
    opened_at: datetime


@dataclass(frozen=True)
class Fill:
    """체결 1건 — 원장에 남는 사실."""

    ticker: str
    side: str
    action: str
    quantity: int
    price: float  # 종목 통화
    fee_krw: float
    realized_pnl_krw: float | None  # 청산(SELL·COVER)에서만
    ts: datetime


@dataclass(frozen=True)
class LedgerError(Exception):
    reason: str


def position_value_krw(position: Position, price: float) -> float:
    if position.side == "LONG":
        return rules.to_krw(position.ticker, price) * position.quantity
    return rules.to_krw(position.ticker, 2 * position.avg_price - price) * position.quantity


def equity_krw(cash_krw: float, positions: list[Position], prices: dict[str, float]) -> float:
    """현재가가 없는 종목은 진입가로 평가한다(열화 — 없는 값을 0으로 만들지 않는다)."""
    total = cash_krw
    for p in positions:
        total += position_value_krw(p, prices.get(p.ticker, p.avg_price))
    return total


def apply(
    cash_krw: float,
    positions: list[Position],
    *,
    ticker: str,
    action: str,
    quantity: int,
    price: float,
    ts: datetime,
) -> tuple[float, list[Position], Fill]:
    """주문 1건을 체결한다. 불가하면 LedgerError — 호출자가 거부 사유로 기록한다."""
    if action not in rules.ACTIONS:
        raise LedgerError(f"알 수 없는 주문 {action}")
    if quantity <= 0:
        raise LedgerError("수량은 1주 이상이어야 합니다")
    if price <= 0:
        raise LedgerError("체결가가 없습니다")

    notional = rules.to_krw(ticker, price) * quantity
    fee = rules.fee_krw(notional)
    side = "LONG" if action in ("BUY", "SELL") else "SHORT"
    held = next((p for p in positions if p.ticker == ticker and p.side == side), None)
    opposite = next((p for p in positions if p.ticker == ticker and p.side != side), None)
    others = [p for p in positions if not (p.ticker == ticker and p.side == side)]

    if action in ("BUY", "SHORT"):
        if opposite is not None:
            raise LedgerError(f"{ticker}에 반대 포지션이 있습니다 — 먼저 청산하세요")
        if notional + fee > cash_krw:
            raise LedgerError("현금이 부족합니다")
        if held is None and len(positions) >= rules.assumed_max_positions:
            raise LedgerError(f"동시 보유 {rules.assumed_max_positions}종목을 넘습니다")
        if held is None:
            new = Position(ticker, side, quantity, price, ts)
        else:
            total_qty = held.quantity + quantity
            avg = (held.avg_price * held.quantity + price * quantity) / total_qty
            new = replace(held, quantity=total_qty, avg_price=avg)
        return (
            cash_krw - notional - fee,
            others + [new],
            Fill(ticker, side, action, quantity, price, fee, None, ts),
        )

    # SELL · COVER — 청산
    if held is None:
        raise LedgerError(f"{ticker} {side} 포지션이 없습니다")
    if quantity > held.quantity:
        raise LedgerError(f"보유 {held.quantity}주보다 많이 청산할 수 없습니다")
    if action == "SELL":
        pnl = rules.to_krw(ticker, price - held.avg_price) * quantity - fee
        cash_after = cash_krw + notional - fee
    else:
        pnl = rules.to_krw(ticker, held.avg_price - price) * quantity - fee
        cash_after = cash_krw + rules.to_krw(ticker, 2 * held.avg_price - price) * quantity - fee
    remaining = held.quantity - quantity
    kept = others + ([replace(held, quantity=remaining)] if remaining else [])
    return cash_after, kept, Fill(ticker, side, action, quantity, price, fee, round(pnl, 2), ts)
