from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.market_price_dto import MarketPricesResponse, MarketPriceQuery


class MarketPriceUseCase(ABC):
    """게임 시세 유스케이스 — 가상 종목의 가격 곡선 조회."""

    @abstractmethod
    async def list_prices(self, query: MarketPriceQuery) -> MarketPricesResponse:
        """전 종목의 현재가와 최근 가격 곡선을 반환한다."""
        ...
