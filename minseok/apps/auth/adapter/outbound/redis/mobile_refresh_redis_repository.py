from datetime import datetime

from redis.asyncio import Redis

from auth.app.ports.output.mobile_refresh_repository import MobileRefreshRepository

# 논리 DB를 나눴어도 프리픽스를 유지한다 — 덤프·마이그레이션 때 출처를 즉시 식별할 수 있어야 한다.
_REFRESH_KEY = "mobile:refresh:{user_id}:{jti}"
_DEVICES_KEY = "mobile:devices:{user_id}"  # 기기 목록 — 유저 단위 전량 폐기·기기 관리용 역인덱스


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
