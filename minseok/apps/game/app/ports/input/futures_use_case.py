from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.futures_dto import (
    CloseFuturesCommand,
    FuturesQuery,
    FuturesReceipt,
    FuturesView,
    OpenFuturesCommand,
)


class FuturesUseCase(ABC):
    """지수 선물 — 근월물 조회·진입·중도청산. 만기 정산은 조회 시점에 확정된다."""

    @abstractmethod
    async def get_market(self, query: FuturesQuery) -> FuturesView:
        ...

    @abstractmethod
    async def open(self, command: OpenFuturesCommand) -> FuturesReceipt:
        ...

    @abstractmethod
    async def close(self, command: CloseFuturesCommand) -> FuturesReceipt:
        ...
