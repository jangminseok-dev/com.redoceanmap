from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.store_open_dto import OpenStoreCommand, OpenStoreReceipt


class StoreOpenUseCase(ABC):
    """창업 유스케이스 — 상권·업종을 골라 가게를 연다."""

    @abstractmethod
    async def open_store(self, command: OpenStoreCommand) -> OpenStoreReceipt:
        """보증금·인테리어를 지불하고 가게를 만든다. 자본이 모자라면 앱 예외."""
        ...
