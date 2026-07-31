from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.store_daily_dto import StoreDailyQuery, StoreDailyView, StoreSummary


class StoreDailyUseCase(ABC):
    """가게 현황 유스케이스 — 일별 매출·비용과 손님 구성."""

    @abstractmethod
    async def list_stores(self, user_id: int) -> tuple[StoreSummary, ...]:
        """내 가게 목록."""
        ...

    @abstractmethod
    async def get_daily(self, query: StoreDailyQuery) -> StoreDailyView:
        """가게 1곳의 현황. 남의 가게·없는 가게는 앱 예외."""
        ...
