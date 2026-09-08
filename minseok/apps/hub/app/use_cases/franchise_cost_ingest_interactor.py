from __future__ import annotations

import logging

from hub.app.dtos.franchise_cost_dto import FranchiseCostItem
from hub.app.ports.input.franchise_cost_ingest_use_case import FranchiseCostIngestUseCase
from hub.app.ports.output.franchise_cost_storage_port import FranchiseCostStoragePort

logger = logging.getLogger(__name__)


class FranchiseCostIngestInteractor(FranchiseCostIngestUseCase):
    def __init__(self, storage: FranchiseCostStoragePort) -> None:
        self._storage = storage

    async def ingest(self, items: list[FranchiseCostItem]) -> int:
        valid = [i for i in items if i.industry_name.strip() and i.total_amount > 0 and i.year > 2000]
        if not valid:
            return 0
        saved = await self._storage.save_many(valid)
        logger.info("[hub-franchise-cost] 수신 %d건 중 %d건 반영", len(items), saved)
        return saved
