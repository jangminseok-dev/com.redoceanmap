from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_ranking_dto import AreaRankingQuery, AreaRankingView


class AreaRankingUseCase(ABC):
    """상권 디렉터리 — 전 상권을 지표와 함께 훑는다(정렬·검색은 소비자 몫)."""

    @abstractmethod
    async def list_ranking(self, query: AreaRankingQuery) -> AreaRankingView:
        """조건에 맞는 상권이 없으면 rows가 빈 리스트(404 아님 — 목록 화면은 떠야 한다)."""
        ...
