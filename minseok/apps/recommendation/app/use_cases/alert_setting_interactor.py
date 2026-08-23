from __future__ import annotations

import logging

from recommendation.app.dtos.alert_setting_dto import AlertSettingDraft
from recommendation.app.ports.input.alert_setting_use_case import AlertSettingUseCase
from recommendation.app.ports.output.alert_setting_repository import AlertSettingRepositoryPort

logger = logging.getLogger(__name__)


class AlertSettingInteractor(AlertSettingUseCase):
    """수신 설정 대장 — 행 부재를 기본 수신(True)으로 해석하는 규칙의 단일 소유자."""

    def __init__(self, settings: AlertSettingRepositoryPort) -> None:
        self._settings = settings

    async def get_mine(self, user_id: int) -> bool:
        stored = await self._settings.find_by_user(user_id)
        return True if stored is None else stored

    async def save(self, draft: AlertSettingDraft) -> bool:
        await self._settings.upsert(draft.user_id, draft.email_alerts)
        logger.info("[alert-setting] user=%d email_alerts=%s", draft.user_id, draft.email_alerts)
        return draft.email_alerts
