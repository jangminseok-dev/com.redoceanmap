from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta


class EmailVerificationTokenRepository(ABC):
    """이메일 인증 토큰 저장소 + 요청 제한 계수 — 만료는 저장소의 TTL에 맡긴다."""

    @abstractmethod
    async def save(self, token_hash: str, user_id: int, email: str, ttl: timedelta) -> None:
        """토큰 해시 → (user_id, 발급 당시 이메일). 이메일을 함께 두는 이유: 주소가 바뀐 뒤의 옛 링크를 거른다."""
        ...

    @abstractmethod
    async def consume(self, token_hash: str) -> tuple[int, str] | None:
        """1회용 — 꺼내면서 지운다. 없거나 만료면 None."""
        ...

    @abstractmethod
    async def try_acquire_request(self, user_id: int, cooldown: timedelta, daily_limit: int) -> bool:
        """이 계정이 지금 인증 메일을 요청해도 되는가 — 되면 횟수를 올리고 True."""
        ...
