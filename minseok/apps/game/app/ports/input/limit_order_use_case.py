from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.limit_order_dto import (
    OrderActionCommand,
    OrderListQuery,
    OrderListResponse,
    OrderReceipt,
    PlaceEntryOrderCommand,
    PlaceExitOrderCommand,
)


class LimitOrderUseCase(ABC):
    """지정가 주문 — 진입 예약과 청산 예약(익절·손절).

    체결은 cron이 아니라 **조회가 도달한 시점에** 판정한다. 그래서 모든 메서드가
    시작할 때 밀린 주문을 먼저 정산한다(멱등).
    """

    @abstractmethod
    async def place_entry(self, command: PlaceEntryOrderCommand) -> OrderReceipt:
        """진입 예약. 체결 시 쓸 현금을 지금 묶는다."""
        ...

    @abstractmethod
    async def place_exit(self, command: PlaceExitOrderCommand) -> OrderReceipt:
        """보유 포지션에 익절·손절을 건다(둘 다 걸면 한쪽 체결 시 나머지 자동 취소)."""
        ...

    @abstractmethod
    async def cancel(self, command: OrderActionCommand) -> OrderReceipt:
        """대기 주문 취소. 진입 예약이면 묶인 현금을 돌려준다."""
        ...

    @abstractmethod
    async def extend(self, command: OrderActionCommand) -> OrderReceipt:
        """만료를 연장한다."""
        ...

    @abstractmethod
    async def list_orders(self, query: OrderListQuery) -> OrderListResponse:
        """대기·최근 주문. 이 호출이 곧 체결 판정 시점이다."""
        ...
