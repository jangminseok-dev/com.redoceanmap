from datetime import datetime, timedelta, timezone

from auth.adapter.outbound.redis.refresh_token_redis_repository import (
    RefreshTokenRedisRepository,
)
from auth.adapter.outbound.redis.token_digest import digest
from auth.domain.entities.refresh_token_entity import RefreshToken


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.exat: dict[str, int] = {}

    async def set(self, key, value, exat=None):
        self.store[key] = value
        self.exat[key] = exat

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        existed = key in self.store or key in self.sets
        self.store.pop(key, None)
        self.sets.pop(key, None)
        return 1 if existed else 0

    async def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    async def srem(self, key, member):
        self.sets.get(key, set()).discard(member)

    async def smembers(self, key):
        return set(self.sets.get(key, set()))

    async def expireat(self, key, when):
        self.exat[key] = when

    async def scan_iter(self, match=None):
        import fnmatch

        for key in list(self.store):
            if match is None or fnmatch.fnmatch(key, match):
                yield key


def _expires_at():
    return datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=14)


async def test_저장하면_만료시각이_키_TTL로_설정된다():
    redis = _FakeRedis()
    repository = RefreshTokenRedisRepository(redis=redis)
    expires_at = _expires_at()
    created = await repository.create(user_id=1, token="tok", expires_at=expires_at)
    assert created.token == "tok"
    assert redis.exat["auth:refresh:" + digest("tok")] == int(expires_at.timestamp())


async def test_토큰_원문은_Redis_어디에도_남지_않는다():
    redis = _FakeRedis()
    repository = RefreshTokenRedisRepository(redis=redis)
    token = "원문토큰-secret"
    stored = await repository.create(user_id=1, token=token, expires_at=_expires_at())
    await repository.mark_rotated(stored)
    dumped = [*redis.store, *redis.store.values(), *(m for s in redis.sets.values() for m in s)]
    assert all(token not in item for item in dumped)


async def test_저장한_토큰은_원형_그대로_조회된다():
    repository = RefreshTokenRedisRepository(redis=_FakeRedis())
    expires_at = _expires_at()
    await repository.create(user_id=7, token="tok", expires_at=expires_at)
    found = await repository.find_by_token("tok")
    assert found is not None
    assert found.user_id == 7
    assert found.expires_at == expires_at
    assert not found.is_expired()


async def test_없는_토큰은_None을_돌려준다():
    repository = RefreshTokenRedisRepository(redis=_FakeRedis())
    assert await repository.find_by_token("없는토큰") is None


async def test_삭제하면_더_이상_조회되지_않는다():
    redis = _FakeRedis()
    repository = RefreshTokenRedisRepository(redis=redis)
    await repository.create(user_id=1, token="tok", expires_at=_expires_at())
    await repository.delete("tok")
    assert await repository.find_by_token("tok") is None
    assert redis.sets.get("auth:refresh:user:1", set()) == set()  # 역인덱스도 정리


async def test_유저_단위_전량_폐기는_모든_토큰과_인덱스를_지운다():
    redis = _FakeRedis()
    repository = RefreshTokenRedisRepository(redis=redis)
    await repository.create(user_id=1, token="tok-a", expires_at=_expires_at())
    await repository.create(user_id=1, token="tok-b", expires_at=_expires_at())
    await repository.create(user_id=2, token="tok-c", expires_at=_expires_at())

    revoked = await repository.delete_all_for_user(1)

    assert revoked == 2
    assert await repository.find_by_token("tok-a") is None
    assert await repository.find_by_token("tok-b") is None
    assert await repository.find_by_token("tok-c") is not None  # 다른 유저는 무관
    assert "auth:refresh:user:1" not in redis.sets


async def test_역인덱스에_없는_레거시_토큰도_SCAN으로_폐기된다():
    redis = _FakeRedis()
    repository = RefreshTokenRedisRepository(redis=redis)
    # 역인덱스 도입 전처럼 토큰만 있고 유저 인덱스 set이 없는 상태를 흉내
    import json

    exat = int(_expires_at().timestamp())
    redis.store["auth:refresh:legacy"] = json.dumps({"user_id": 1, "expires_at": "x"})
    redis.exat["auth:refresh:legacy"] = exat

    revoked = await repository.delete_all_for_user(1)

    assert revoked == 1
    assert await repository.find_by_token("legacy") is None


async def test_회전_기록은_유저와_시각을_돌려주고_전량_폐기_SCAN에_걸리지_않는다():
    redis = _FakeRedis()
    repository = RefreshTokenRedisRepository(redis=redis)
    stored = await repository.create(user_id=3, token="old", expires_at=_expires_at())
    await repository.mark_rotated(stored)
    await repository.delete("old")

    rotated = await repository.find_rotated("old")
    assert rotated is not None and rotated.user_id == 3
    assert await repository.find_rotated("모르는토큰") is None
    assert await repository.delete_all_for_user(3) == 0  # 회전 기록은 세션이 아니다
