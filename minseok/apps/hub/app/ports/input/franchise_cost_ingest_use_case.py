from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.franchise_cost_dto import FranchiseCostItem


class FranchiseCostIngestUseCase(ABC):
    @abstractmethod
    async def ingest(self, items: list[FranchiseCostItem]) -> int: ...
