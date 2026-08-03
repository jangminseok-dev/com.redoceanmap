from abc import ABC, abstractmethod
from datetime import datetime


class MobileRefreshRepository(ABC):
    """모바일 세션 저장소 — 웹 세션과 논리적으로 분리된 저장소를 쓴다(플랫폼 분리 원칙)."""

    @abstractmethod
    async def save(
        self,
        user_id: int,
        jti: str,
        device_id: str,
        user_agent: str,
        expires_at: datetime,
    ) -> None: ...
