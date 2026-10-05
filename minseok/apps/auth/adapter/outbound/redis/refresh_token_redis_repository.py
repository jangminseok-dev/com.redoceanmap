import json
from datetime import datetime, timezone

from redis.asyncio import Redis

from auth.adapter.outbound.redis.token_digest import digest
from auth.app.ports.output.refresh_token_repository import RefreshTokenRepository
from auth.domain.entities.refresh_token_entity import RefreshToken, RotatedRefreshToken

_KEY_PREFIX = "auth:refresh:"
_USER_INDEX_PREFIX = "auth:refresh:user:"  # user_id → 토큰 해시 set (유저 단위 전량 폐기용 역인덱스)
# 회전으로 폐기된 토큰 — 재사용 탐지용. `auth:refresh:*` SCAN에 걸리지 않게 접두를 가른다.
_ROTATED_PREFIX = "auth:refresh-rotated:"


class RefreshTokenRedisRepository(RefreshTokenRepository):
    """리프레시 토큰을 Redis에 저장 — 만료 폐기는 키 TTL(EXPIREAT)에 위임한다.

    유저별 역인덱스 set을 함께 유지한다(정지/탈퇴 시 강제 로그아웃).
    인덱스 TTL은 토큰과 같은 시점으로 갱신되므로 유령 항목은 조회 시 걸러진다.
    키는 토큰 원문이 아니라 SHA-256 해시다 — Redis 내용이 새어도 그 값으로 세션을 이어받을 수 없다.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def create(self, user_id: int, token: str, expires_at: datetime) -> RefreshToken:
        value = json.dumps({"user_id": user_id, "expires_at": expires_at.isoformat()})
        exat = int(expires_at.timestamp())
        index_key = _USER_INDEX_PREFIX + str(user_id)
        await self._redis.set(_KEY_PREFIX + digest(token), value, exat=exat)
        await self._redis.sadd(index_key, digest(token))
        await self._redis.expireat(index_key, exat)  # 마지막 토큰 만료와 함께 소멸
        return RefreshToken(user_id=user_id, token=token, expires_at=expires_at)

    async def find_by_token(self, token: str) -> RefreshToken | None:
        raw = await self._redis.get(_KEY_PREFIX + digest(token))
        if raw is None:
            return None
        data = json.loads(raw)
        return RefreshToken(
            user_id=int(data["user_id"]),
            token=token,
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )

    async def delete(self, token: str) -> None:
        hashed = digest(token)
        raw = await self._redis.get(_KEY_PREFIX + hashed)
        await self._redis.delete(_KEY_PREFIX + hashed)
        if raw is not None:
            user_id = json.loads(raw)["user_id"]
            await self._redis.srem(_USER_INDEX_PREFIX + str(user_id), hashed)

    async def mark_rotated(self, token: RefreshToken) -> None:
        value = json.dumps(
            {"user_id": token.user_id, "rotated_at": datetime.now(timezone.utc).isoformat()}
        )
        # 원래 만료 시각까지만 남긴다 — 그 뒤에는 어차피 만료로 거절된다.
        await self._redis.set(
            _ROTATED_PREFIX + digest(token.token), value, exat=int(token.expires_at.timestamp())
        )

    async def find_rotated(self, token: str) -> RotatedRefreshToken | None:
        raw = await self._redis.get(_ROTATED_PREFIX + digest(token))
        if raw is None:
            return None
        data = json.loads(raw)
        return RotatedRefreshToken(
            user_id=int(data["user_id"]), rotated_at=datetime.fromisoformat(data["rotated_at"])
        )

    async def delete_all_for_user(self, user_id: int) -> int:
        index_key = _USER_INDEX_PREFIX + str(user_id)
        keys = {_KEY_PREFIX + t for t in await self._redis.smembers(index_key)}
        # 역인덱스 도입 전 발급된 레거시 토큰(인덱스에 없음)까지 SCAN으로 훑는다 —
        # 배포 과도기에도 강제 로그아웃이 누락되지 않도록. 관리 작업이라 저빈도.
        async for key in self._redis.scan_iter(match=_KEY_PREFIX + "*"):
            if key.startswith(_USER_INDEX_PREFIX):
                continue  # 유저 역인덱스 set 키는 대상 아님
            raw = await self._redis.get(key)
            if raw is not None and json.loads(raw).get("user_id") == user_id:
                keys.add(key)
        revoked = 0
        for key in keys:
            revoked += await self._redis.delete(key)
        await self._redis.delete(index_key)
        return revoked
