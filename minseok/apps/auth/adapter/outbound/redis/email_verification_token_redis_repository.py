import json
from datetime import timedelta

from redis.asyncio import Redis

from auth.app.ports.output.email_verification_token_repository import EmailVerificationTokenRepository

_TOKEN_PREFIX = "auth:email-verify:token:"
_COOLDOWN_PREFIX = "auth:email-verify:cooldown:"
_DAILY_PREFIX = "auth:email-verify:daily:"
_DAY_SECONDS = 86_400


class EmailVerificationTokenRedisRepository(EmailVerificationTokenRepository):
    """인증 토큰을 Redis에 — 만료는 키 TTL에 위임한다(리프레시 토큰 저장소와 같은 방식)."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def save(self, token_hash: str, user_id: int, email: str, ttl: timedelta) -> None:
        value = json.dumps({"user_id": user_id, "email": email})
        await self._redis.set(_TOKEN_PREFIX + token_hash, value, ex=int(ttl.total_seconds()))

    async def consume(self, token_hash: str) -> tuple[int, str] | None:
        raw = await self._redis.getdel(_TOKEN_PREFIX + token_hash)  # 읽기와 삭제가 한 번에 — 같은 링크의 동시 사용을 막는다
        if raw is None:
            return None
        data = json.loads(raw)
        return int(data["user_id"]), str(data["email"])

    async def try_acquire_request(self, user_id: int, cooldown: timedelta, daily_limit: int) -> bool:
        # 재요청 간격 — 키가 이미 있으면(NX 실패) 아직 기다려야 한다
        if not await self._redis.set(_COOLDOWN_PREFIX + str(user_id), "1", ex=int(cooldown.total_seconds()), nx=True):
            return False
        daily_key = _DAILY_PREFIX + str(user_id)
        count = await self._redis.incr(daily_key)
        if count == 1:
            await self._redis.expire(daily_key, _DAY_SECONDS)
        return count <= daily_limit
