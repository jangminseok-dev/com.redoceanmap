from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LimitOrderRecord:
    """저장된 주문 1건 — 어댑터가 ORM에서 옮겨 담는다."""

    id: int
    user_id: int
    kind: str
    symbol: str
    side: str
    position_id: int | None
    trigger: str
    limit_price_krw: int
    quantity: int
    leverage: int
    placed_tick: int
    expires_tick: int
    status: str
    filled_tick: int | None
    filled_price_krw: int | None
    reserved_cash_krw: int


class GameLimitOrderRepository(ABC):
    """지정가 주문 영속 포트.

    현금 이동(예약금 묶기·해제)은 이 포트가 하지 않는다 — 지갑·원장은 `GameAccountRepository`
    한 곳이 소유한다(불변식 `SUM(ledger) == cash`를 두 포트가 나눠 가지면 깨진다).
    """

    @abstractmethod
    async def place(
        self,
        user_id: int,
        epoch_id: int,
        kind: str,
        symbol: str,
        side: str,
        trigger: str,
        limit_price_krw: int,
        quantity: int,
        placed_tick: int,
        expires_tick: int,
        leverage: int = 1,
        position_id: int | None = None,
        reserved_cash_krw: int = 0,
    ) -> LimitOrderRecord:
        """대기 주문 1건을 만든다."""
        ...

    @abstractmethod
    async def list_pending(self, user_id: int, epoch_id: int) -> tuple[LimitOrderRecord, ...]:
        """체결 판정 대상 — 이 유저의 대기 주문 전부."""
        ...

    @abstractmethod
    async def list_recent(
        self, user_id: int, epoch_id: int, limit: int = 20
    ) -> tuple[LimitOrderRecord, ...]:
        """최근 종료된 주문(체결·취소·만료) 목록."""
        ...

    @abstractmethod
    async def find(self, user_id: int, order_id: int) -> LimitOrderRecord | None:
        """남의 주문을 건드리지 못하게 user_id를 함께 받는다."""
        ...

    @abstractmethod
    async def mark_filled(self, order_id: int, filled_tick: int, filled_price_krw: int) -> None:
        """체결 확정. 이미 종료된 주문이면 `LookupError`."""
        ...

    @abstractmethod
    async def mark_closed(self, order_id: int, status: str) -> None:
        """cancelled · expired로 종료한다. 이미 종료된 주문이면 `LookupError`."""
        ...

    @abstractmethod
    async def cancel_for_position(self, position_id: int, except_order_id: int | None = None) -> int:
        """그 포지션에 걸린 나머지 대기 주문을 취소한다(OCO). 취소한 건수를 돌려준다."""
        ...

    @abstractmethod
    async def extend(self, order_id: int, expires_tick: int) -> None:
        """만료를 미룬다 — 만료는 스캔 범위를 묶는 장치라 없앨 수 없고 연장만 한다."""
        ...
