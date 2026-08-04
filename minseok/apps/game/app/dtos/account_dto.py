"""계정 상태 DTO — 지갑·포지션. wallet과 trade 두 슬라이스가 함께 쓴다.

거래는 지갑·포지션·원장을 **한 트랜잭션으로** 바꿔야 해서 셋을 한 리포지토리가 다루고,
그 계약이 여기 산다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenPosition:
    id: int
    symbol: str
    side: str  # LONG | SHORT
    quantity: int
    entry_tick: int
    entry_price_krw: int
    entry_fee_krw: int
    leverage: int = 1               # 1이면 청산도 만료도 없다(도입 전과 같은 동작)
    expires_tick: int | None = None


@dataclass(frozen=True)
class RecentlyClosed:
    """유저가 직접 청산하지 않은 마감 — 복귀했을 때 "그동안 터졌다"를 알린다."""

    id: int
    symbol: str
    name: str
    side: str
    quantity: int
    leverage: int
    closed_tick: int
    closed_game_day: int
    exit_price_krw: int
    realized_pnl_krw: int
    reason: str  # liquidated | expired | settled


@dataclass(frozen=True)
class ClosedPosition:
    id: int
    symbol: str
    side: str
    quantity: int
    entry_tick: int
    entry_price_krw: int
    closed_tick: int
    exit_price_krw: int
    realized_pnl_krw: int


@dataclass(frozen=True)
class Account:
    user_id: int
    cash_krw: int
    epoch_id: int
    rule_version: str
    open_positions: tuple[OpenPosition, ...]
