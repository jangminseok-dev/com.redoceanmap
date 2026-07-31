from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.store_dto import SettlementRecord, StoreRecord


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

    @abstractmethod
    async def list_settlements(
        self, user_id: int, epoch_id: int
    ) -> tuple[SettlementRecord, ...]:
        """이 시즌의 결산 전부(가게 무관, 분기 오름차순)."""
        ...

    @abstractmethod
    async def record_settlement(
        self,
        *,
        user_id: int,
        epoch_id: int,
        store_id: int,
        settlement: SettlementRecord,
        settled_through_day: int,
        game_day: int,
    ) -> None:
        """결산 저장 + 지갑에 순익 반영 + 원장 기록 + 앵커 갱신을 한 트랜잭션으로.

        같은 분기를 두 번 정산하면 DB 유니크 제약이 막는다 — 지연 실행이라 조회가 잦고
        멱등성이 곧 정확성이다.
        """
        ...
