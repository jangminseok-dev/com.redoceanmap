from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.app.dtos.price_alert_dto import PriceAlertDraft, StoredPriceAlert


class PriceAlertUseCase(ABC):
    """가격 도달 알림 조건 유스케이스 — 등록·조회·삭제(재활성화는 삭제 후 재등록)."""

    @abstractmethod
    async def list_mine(self, user_id: int) -> list[StoredPriceAlert]:
        ...

    @abstractmethod
    async def create(self, draft: PriceAlertDraft) -> StoredPriceAlert:
        """검증 실패(방향 어휘·가격≤0·티커 공백)는 ValueError, 상한 초과는 PriceAlertLimitError."""
        ...

    @abstractmethod
    async def remove(self, user_id: int, alert_id: int) -> bool:
        ...
