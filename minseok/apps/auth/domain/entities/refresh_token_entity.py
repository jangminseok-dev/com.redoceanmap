from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True)
class RefreshToken:
    """리프레시 토큰 도메인 엔티티 — 회전(사용 즉시 폐기·재발급) 대상."""

    user_id: int
    token: str
    expires_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:  # DB가 naive로 돌려줘도 UTC 기준으로 비교
            expires = expires.replace(tzinfo=timezone.utc)
        return current >= expires


@dataclass(frozen=True, slots=True)
class RotatedRefreshToken:
    """회전으로 폐기된 리프레시 토큰의 흔적 — 재사용 탐지용.

    폐기된 토큰이 다시 오면 사본이 돌아다닌다는 뜻이다. 다만 회전 직후 짧은 유예 안의 재사용은
    탈취가 아니라 같은 브라우저의 동시 갱신이다 — 액세스 토큰이 만료되면 여러 요청이 동시에 401을 받고
    각자 갱신을 시도하므로, 첫 요청만 회전에 성공하고 나머지는 직전 토큰을 들고 온다.
    """

    user_id: int
    rotated_at: datetime

    def is_suspicious_reuse(self, grace: timedelta, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return current - self.rotated_at > grace
