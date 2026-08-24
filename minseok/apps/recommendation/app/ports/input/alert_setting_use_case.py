from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.app.dtos.alert_setting_dto import AlertSettingDraft
from recommendation.app.ports.output.alert_setting_repository import StoredAlertSetting


class AlertSettingUseCase(ABC):
    """알림 수신 설정 유스케이스 — 조회(기본 수신)·저장(토글+텔레그램 등록)."""

    @abstractmethod
    async def get_mine(self, user_id: int) -> StoredAlertSetting:
        """내 수신 설정 — 행이 없으면 기본값(수신 켬·텔레그램 미등록)."""
        ...

    @abstractmethod
    async def save(self, draft: AlertSettingDraft) -> StoredAlertSetting:
        """설정을 저장하고 저장된 값을 반환한다(재저장은 덮어쓰기 — 멱등)."""
        ...
