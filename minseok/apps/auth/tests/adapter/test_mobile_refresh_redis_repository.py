from datetime import datetime, timedelta, timezone

from auth.adapter.outbound.redis.mobile_refresh_redis_repository import MobileRefreshRedisRepository


class _FakeRedis:
    def __init__(self):
        self.hashes: dict[str, dict] = {}
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    async def hset(self, key, mapping):
        self.hashes[key] = dict(mapping)

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def ttl(self, key):
        return 3600 if key in self.hashes else -2

    async def expireat(self, key, when):
        pass

    async def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    async def srem(self, key, member):
        self.sets.get(key, set()).discard(member)

    async def smembers(self, key):
        return set(self.sets.get(key, set()))

    async def delete(self, *keys):
        for key in keys:
            self.hashes.pop(key, None)
            self.strings.pop(key, None)
            self.sets.pop(key, None)

    async def set(self, key, value, exat=None):
        self.strings[key] = value

    async def exists(self, key):
        return int(key in self.strings)


def _expires_at():
    return datetime.now(timezone.utc) + timedelta(days=14)


def _all_keys_and_members(redis):
    return [*redis.hashes, *redis.strings, *redis.sets, *(m for s in redis.sets.values() for m in s)]


async def test_jti_원문은_Redis_어디에도_남지_않는다():
    redis = _FakeRedis()
    repository = MobileRefreshRedisRepository(redis=redis)
    jti = "원문jti-secret"
    await repository.save(1, jti, "device", "ua", _expires_at())
    await repository.deny(jti, _expires_at())
    assert all(jti not in item for item in _all_keys_and_members(redis))


async def test_해시로_저장해도_조회_재사용탐지_전량폐기가_원문_jti로_동작한다():
    redis = _FakeRedis()
    repository = MobileRefreshRedisRepository(redis=redis)
    await repository.save(1, "jti-a", "device-a", "ua", _expires_at())
    await repository.save(1, "jti-b", "device-b", "ua", _expires_at())

    found = await repository.find(1, "jti-a")
    assert found is not None and found.device_id == "device-a"

    await repository.deny("jti-a", _expires_at())
    assert await repository.is_denied("jti-a")
    assert not await repository.is_denied("jti-b")

    await repository.revoke_all(1)
    assert await repository.find(1, "jti-a") is None
    assert await repository.find(1, "jti-b") is None
