from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.app.dtos.price_alert_dto import PriceAlertDraft, StoredPriceAlert


class PriceAlertRepositoryPort(ABC):
    """가격 조건 영속 포트 — 조회는 본인 것만, 스캔 횡단 조회는 허브 게이트웨이 몫."""

    @abstractmethod
    async def list_by_user(self, user_id: int) -> list[StoredPriceAlert]:
        """내 조건 전부(활성·트리거된 것 포함) — 최신 등록 순."""
        ...

    @abstractmethod
    async def count_active(self, user_id: int) -> int:
        ...

    @abstractmethod
    async def add(self, draft: PriceAlertDraft) -> StoredPriceAlert:
        ...

    @abstractmethod
    async def delete(self, user_id: int, alert_id: int) -> bool:
        """본인 소유 조건만 지운다 — 남의 id·미존재는 False(호출부가 404로 해석)."""
        ...
