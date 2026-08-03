from abc import ABC, abstractmethod
from datetime import datetime

from auth.domain.entities.user_entity import User


class UserRepository(ABC):

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def find_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    async def find_by_kakao_id(self, kakao_id: int) -> User | None:
        """카카오 회원번호로 조회 — 모바일 로그인의 유일한 식별 경로(이메일 연동 아님)."""
        ...

    @abstractmethod
    async def create(
        self,
        email: str | None,
        password_hash: str,
        name: str,
        terms_agreed_at: datetime | None = None,
        marketing_agreed: bool = False,
        kakao_id: int | None = None,
    ) -> User: ...

    @abstractmethod
    async def touch_last_login(self, user_id: int) -> None: ...
