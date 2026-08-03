from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.store_action_dto import (
    CloseStoreCommand,
    CloseStoreReceipt,
    StoreDecisionCommand,
    StoreDecisionReceipt,
)


class StoreActionUseCase(ABC):
    """창업 이후의 운영 결정 — 가격·직원·시설 조정과 폐업."""

    @abstractmethod
    async def decide(self, command: StoreDecisionCommand) -> StoreDecisionReceipt:
        ...

    @abstractmethod
    async def close(self, command: CloseStoreCommand) -> CloseStoreReceipt:
        ...
