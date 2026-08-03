from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaceEntryOrderCommand:
    """진입 예약 — "얼마 이하로 내려오면 산다" / "얼마 이상이면 (공매도로) 판다"."""

    user_id: int
    symbol: str
    side: str  # LONG | SHORT
    quantity: int
    limit_price_krw: int
    leverage: int = 1


@dataclass(frozen=True)
class PlaceExitOrderCommand:
    """청산 예약 — 보유 포지션에 거는 익절·손절. 둘 다 걸면 한 쌍(OCO)이 된다."""

    user_id: int
    position_id: int
    take_profit_krw: int | None = None
    stop_loss_krw: int | None = None


@dataclass(frozen=True)
class OrderActionCommand:
    """취소·연장 — 남의 주문을 건드릴 수 없게 user_id를 함께 받는다."""

    user_id: int
    order_id: int


@dataclass(frozen=True)
class OrderListQuery:
    user_id: int


@dataclass(frozen=True)
class LimitOrderView:
    """대기·종료 주문 1건."""

    id: int
    kind: str  # ENTRY | EXIT
    symbol: str
    name: str
    side: str
    position_id: int | None
    trigger: str  # le | ge
    limit_price_krw: int
    quantity: int
    leverage: int
    placed_tick: int
    expires_tick: int
    status: str  # pending | filled | cancelled | expired
    filled_tick: int | None
    filled_price_krw: int | None
    reserved_cash_krw: int


@dataclass(frozen=True)
class OrderListResponse:
    """조회가 곧 체결 시점이다 — `settled`는 이번 조회에서 확정된 건수다."""

    tick: int
    pending: tuple[LimitOrderView, ...]
    recent: tuple[LimitOrderView, ...]
    settled_count: int


@dataclass(frozen=True)
class OrderReceipt:
    """접수·취소·연장 결과."""

    orders: tuple[LimitOrderView, ...]
    cash_krw: int
