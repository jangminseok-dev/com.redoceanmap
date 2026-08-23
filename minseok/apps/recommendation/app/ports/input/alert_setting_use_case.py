from __future__ import annotations

from abc import ABC, abstractmethod

from recommendation.app.dtos.alert_setting_dto import AlertSettingDraft


class AlertSettingUseCase(ABC):
    """알림 수신 설정 유스케이스 — 조회(기본 수신)·저장(토글)."""

    @abstractmethod
    async def get_mine(self, user_id: int) -> bool:
        """내 이메일 알림 수신 여부 — 행이 없으면 True(기본 수신)."""
        ...

    @abstractmethod
    async def save(self, draft: AlertSettingDraft) -> bool:
        """수신 여부를 저장하고 저장된 값을 반환한다(재저장은 덮어쓰기 — 멱등)."""
        ...
