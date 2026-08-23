from __future__ import annotations

from abc import ABC, abstractmethod


class AlertSettingRepositoryPort(ABC):
    """알림 수신 설정 영속 포트 — 회원당 1행, 행 부재 = 기본 수신(True)."""

    @abstractmethod
    async def find_by_user(self, user_id: int) -> bool | None:
        """저장된 수신 여부 — 행이 없으면 None(호출부가 기본 True로 해석)."""
        ...

    @abstractmethod
    async def upsert(self, user_id: int, email_alerts: bool) -> None:
        ...
