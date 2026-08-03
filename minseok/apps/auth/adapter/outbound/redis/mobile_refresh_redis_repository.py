from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from auth.app.dtos.mobile_auth_dto import MobileRefreshSessionDto
from auth.app.ports.output.mobile_refresh_repository import MobileRefreshRepository

# 논리 DB를 나눴어도 프리픽스를 유지한다 — 덤프·마이그레이션 때 출처를 즉시 식별할 수 있어야 한다.
_REFRESH_KEY = "mobile:refresh:{user_id}:{jti}"
_DEVICES_KEY = "mobile:devices:{user_id}"  # 기기 목록 — 유저 단위 전량 폐기·기기 관리용 역인덱스
_DENYLIST_KEY = "mobile:denylist:{jti}"  # 회전으로 폐기된 jti — 재사용 탐지용


class MobileRefreshRedisRepository(MobileRefreshRepository):
    """모바일 리프레시 토큰을 Redis 모바일 DB(db 1)에 저장한다.

    만료 폐기는 키 TTL(EXPIREAT)에 위임한다 — 웹 저장소(db 0)와 같은 방식이되 키 공간이 다르다.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def save(
        self,
        user_id: int,
        jti: str,
        device_id: str,
        user_agent: str,
        expires_at: datetime,
    ) -> None:
        exat = int(expires_at.timestamp())
        key = _REFRESH_KEY.format(user_id=user_id, jti=jti)
        devices = _DEVICES_KEY.format(user_id=user_id)
        await self._redis.hset(
            key,
            mapping={
                "deviceId": device_id,
                "issuedAt": datetime.now(tz=expires_at.tzinfo).isoformat(),
                "userAgent": user_agent,
            },
        )
        await self._redis.expireat(key, exat)
        await self._redis.sadd(devices, jti)
        await self._redis.expireat(devices, exat)  # 마지막 기기 만료와 함께 소멸

    async def find(self, user_id: int, jti: str) -> MobileRefreshSessionDto | None:
        key = _REFRESH_KEY.format(user_id=user_id, jti=jti)
        stored = await self._redis.hgetall(key)
        if not stored:
            return None
        ttl = await self._redis.ttl(key)
        # -2는 부재, -1은 TTL 없는 키다. 후자는 save()가 만들 수 없는 형태이므로 신뢰하지 않는다
        # (만료가 없다는 뜻이라, 통과시키면 영구 토큰이 된다).
        if ttl <= 0:
            return None
        return MobileRefreshSessionDto(
            device_id=stored.get("deviceId", ""),
            user_agent=stored.get("userAgent", ""),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
        )

    async def delete(self, user_id: int, jti: str) -> None:
        await self._redis.delete(_REFRESH_KEY.format(user_id=user_id, jti=jti))
        # 역인덱스에 죽은 jti를 남기지 않는다 — 전량 폐기 때 헛도는 삭제가 쌓인다.
        await self._redis.srem(_DEVICES_KEY.format(user_id=user_id), jti)

    async def deny(self, jti: str, expires_at: datetime) -> None:
        await self._redis.set(
            _DENYLIST_KEY.format(jti=jti), "1", exat=int(expires_at.timestamp())
        )

    async def is_denied(self, jti: str) -> bool:
        return bool(await self._redis.exists(_DENYLIST_KEY.format(jti=jti)))

    async def revoke_all(self, user_id: int) -> None:
        devices = _DEVICES_KEY.format(user_id=user_id)
        jtis = await self._redis.smembers(devices)
        if jtis:
            await self._redis.delete(
                *(_REFRESH_KEY.format(user_id=user_id, jti=jti) for jti in jtis)
            )
        await self._redis.delete(devices)
