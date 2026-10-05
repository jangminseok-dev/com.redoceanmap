from abc import ABC, abstractmethod
from datetime import datetime

from auth.domain.entities.refresh_token_entity import RefreshToken, RotatedRefreshToken


class RefreshTokenRepository(ABC):

    @abstractmethod
    async def create(self, user_id: int, token: str, expires_at: datetime) -> RefreshToken: ...

    @abstractmethod
    async def find_by_token(self, token: str) -> RefreshToken | None: ...

    @abstractmethod
    async def delete(self, token: str) -> None: ...

    @abstractmethod
    async def delete_all_for_user(self, user_id: int) -> int:
        """유저의 리프레시 토큰 전량 폐기(강제 로그아웃) — 폐기 건수를 반환한다."""
        ...

    @abstractmethod
    async def mark_rotated(self, token: RefreshToken) -> None:
        """회전으로 폐기하는 토큰을 원래 만료 시각까지 기록한다(재사용 탐지용)."""
        ...

    @abstractmethod
    async def find_rotated(self, token: str) -> RotatedRefreshToken | None: ...
