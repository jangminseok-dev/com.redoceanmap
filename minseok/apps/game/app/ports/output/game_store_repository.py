from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.store_dto import StoreRecord


class GameStoreRepository(ABC):
    """가게 영속. 창업은 지갑·원장과 한 트랜잭션이라 지갑 리포지토리와 협력한다."""

    @abstractmethod
    async def create_store(
        self,
        *,
        user_id: int,
        epoch_id: int,
        trdar_code: int,
        service_code: str,
        opened_game_day: int,
        store_scale: float,
        deposit_krw: int,
        interior_krw: int,
        profile_snapshot: dict,
        decision: dict,
        cash_delta_krw: int,
    ) -> StoreRecord:
        """가게 + 초기 결정 + 지갑 차감 + 원장 기록을 한 트랜잭션으로."""
        ...

    @abstractmethod
    async def list_stores(self, user_id: int, epoch_id: int) -> tuple[StoreRecord, ...]:
        """이 시즌 내 가게 전부(폐업 포함)."""
        ...

    @abstractmethod
    async def find_store(self, user_id: int, store_id: int, epoch_id: int) -> StoreRecord | None:
        """남의 가게는 조회되지 않는다."""
        ...
