from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.franchise_cost_dto import FranchiseCostItem


class FranchiseCostStoragePort(ABC):
    """허브가 스포크(market)에 위임하는 창업비용 저장 추상 — 수집 배치의 적재 창구."""

    @abstractmethod
    async def save_many(self, items: list[FranchiseCostItem]) -> int:
        """(연도, 부문, 업종) 단위 교체 저장. 반영 건수를 반환한다."""
        ...
