from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.trade_dto import CloseTradeCommand, OpenTradeCommand, TradeReceipt


class TradeUseCase(ABC):
    """매매 유스케이스 — 롱/숏 진입과 청산. 실제 증권 주문이 아니다."""

    @abstractmethod
    async def open(self, command: OpenTradeCommand) -> TradeReceipt:
        """포지션을 연다. 현금이 모자라거나 시즌이 끝났으면 앱 예외."""
        ...

    @abstractmethod
    async def close(self, command: CloseTradeCommand) -> TradeReceipt:
        """포지션을 닫는다. 남의 포지션·이미 닫힌 포지션은 앱 예외."""
        ...
