from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StoredAlertSetting:
    """저장된 수신 설정 1행 — 행 부재의 기본값 해석은 인터랙터 몫."""

    email_alerts: bool
    telegram_chat_id: str | None  # NULL = 텔레그램 미등록(I-7)


class AlertSettingRepositoryPort(ABC):
    """알림 수신 설정 영속 포트 — 회원당 1행, 행 부재 = 기본 수신(True)·텔레그램 미등록."""

    @abstractmethod
    async def find_by_user(self, user_id: int) -> StoredAlertSetting | None:
        """저장된 설정 — 행이 없으면 None(호출부가 기본값으로 해석)."""
        ...

    @abstractmethod
    async def upsert(
        self, user_id: int, email_alerts: bool, telegram_chat_id: str | None
    ) -> None:
        ...
