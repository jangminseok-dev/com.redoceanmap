from abc import ABC, abstractmethod
from datetime import datetime

from auth.app.dtos.mobile_auth_dto import MobileRefreshSessionDto


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

    @abstractmethod
    async def find(self, user_id: int, jti: str) -> MobileRefreshSessionDto | None:
        """살아 있는 세션만 돌려준다 — 만료·부재는 똑같이 None이다(갱신 측에서 구분하지 않는다)."""
        ...

    @abstractmethod
    async def delete(self, user_id: int, jti: str) -> None:
        """회전 — 방금 쓴 토큰을 폐기한다. 없으면 조용히 통과한다(멱등)."""
        ...

    @abstractmethod
    async def deny(self, jti: str, expires_at: datetime) -> None:
        """폐기된 토큰을 재사용 탐지용으로 기억한다. 원래 만료 시각까지만 붙든다."""
        ...

    @abstractmethod
    async def is_denied(self, jti: str) -> bool: ...

    @abstractmethod
    async def revoke_all(self, user_id: int) -> None:
        """이 유저의 모바일 세션 전량 폐기 — 재사용이 탐지됐을 때만 부른다.

        웹 세션(db 0)은 건드리지 않는다. 탈취된 플랫폼만 끊는 것이 명세 4.4의 원칙이다.
        """
        ...
