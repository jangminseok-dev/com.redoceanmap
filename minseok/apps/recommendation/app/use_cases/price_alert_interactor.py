from __future__ import annotations

import logging

from recommendation.app.dtos.price_alert_dto import PriceAlertDraft, StoredPriceAlert
from recommendation.app.ports.input.price_alert_use_case import PriceAlertUseCase
from recommendation.app.ports.output.price_alert_repository import PriceAlertRepositoryPort

logger = logging.getLogger(__name__)

# 회원당 활성 조건 상한 — 스캔 비용과 스팸 방지(북마크 MAX_BOOKMARKS=200 선례의 축소판:
# 조건은 대상보다 세분화된 단위라 더 작게 잡는다)
MAX_ACTIVE_ALERTS = 50

DIRECTIONS = ("above", "below")


class PriceAlertLimitError(Exception):
    """활성 조건 상한 초과 — 라우터가 409로 변환한다(북마크 한도 선례)."""


class PriceAlertInteractor(PriceAlertUseCase):
    """가격 조건 대장 — 검증·상한의 단일 소유자. 도달 판정은 허브 스캔 몫."""

    def __init__(self, alerts: PriceAlertRepositoryPort) -> None:
        self._alerts = alerts

    async def list_mine(self, user_id: int) -> list[StoredPriceAlert]:
        return await self._alerts.list_by_user(user_id)

    async def create(self, draft: PriceAlertDraft) -> StoredPriceAlert:
        ticker = draft.ticker.strip().upper()  # 북마크 stock 대문자 정규화와 동일 규칙
        if not ticker:
            raise ValueError("종목을 입력해 주세요.")
        if draft.direction not in DIRECTIONS:
            raise ValueError("방향은 above(이상) 또는 below(이하)만 가능합니다.")
        if not draft.target_price > 0:
            raise ValueError("가격은 0보다 커야 합니다.")
        if await self._alerts.count_active(draft.user_id) >= MAX_ACTIVE_ALERTS:
            raise PriceAlertLimitError(
                f"활성 가격 알림은 최대 {MAX_ACTIVE_ALERTS}개입니다."
            )
        stored = await self._alerts.add(PriceAlertDraft(
            user_id=draft.user_id, ticker=ticker,
            target_price=draft.target_price, direction=draft.direction,
        ))
        logger.info(
            "[price-alert] user=%d %s %s %.4f 등록",
            draft.user_id, ticker, draft.direction, draft.target_price,
        )
        return stored

    async def remove(self, user_id: int, alert_id: int) -> bool:
        return await self._alerts.delete(user_id, alert_id)
