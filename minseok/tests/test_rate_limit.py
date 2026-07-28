"""core/rate_limit 검증 — 한도 내 통과, 초과 429(Retry-After), IP 분리, Redis 장애 시 열림.

가짜 Redis(카운터 dict)를 주입해 실제 서버 없이 창 계산·키 분리를 확인한다.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from core import rate_limit as rate_limit_module
from core.rate_limit import rate_limit


class _FakeRedis:
    """incr/expire만 쓰는 최소 대역 — 만료는 창 인덱스가 키에 들어가므로 검증에 무관하다."""

    def __init__(self, broken: bool = False):
        self.counters: dict[str, int] = {}
        self.expires: dict[str, int] = {}
        self.broken = broken

    async def incr(self, key: str) -> int:
        if self.broken:
            raise RedisConnectionError("redis down")
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expires[key] = seconds


@pytest.fixture
def fake_redis(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(rate_limit_module, "get_redis", lambda: redis)
    return redis


def _client() -> TestClient:
    app = FastAPI()

    @app.post("/try", dependencies=[rate_limit("test", limit=3, window_seconds=60)])
    def _try():
        return {"ok": True}

    return TestClient(app)


def test_한도_내는_통과하고_초과분은_429(fake_redis):
    client = _client()
    for _ in range(3):
        assert client.post("/try").status_code == 200
    blocked = client.post("/try")
    assert blocked.status_code == 429
    assert 0 < int(blocked.headers["Retry-After"]) <= 60


def test_첫_요청에만_TTL을_건다(fake_redis):
    client = _client()
    client.post("/try")
    client.post("/try")
    assert list(fake_redis.expires.values()) == [60]  # 두 번째 요청이 TTL을 연장하지 않는다


def test_IP가_다르면_카운터가_분리된다(fake_redis):
    client = _client()
    for _ in range(3):
        client.post("/try", headers={"CF-Connecting-IP": "1.1.1.1"})
    assert client.post("/try", headers={"CF-Connecting-IP": "1.1.1.1"}).status_code == 429
    assert client.post("/try", headers={"CF-Connecting-IP": "2.2.2.2"}).status_code == 200


def test_X_Forwarded_For는_첫_홉을_쓴다(fake_redis):
    client = _client()
    client.post("/try", headers={"X-Forwarded-For": "3.3.3.3, 10.0.0.1"})
    assert any(key.endswith(":3.3.3.3") for key in fake_redis.counters)


def test_Redis가_죽으면_막지_않는다(monkeypatch):
    """열림 정책 — auth는 이미 Redis 의존이라 여기서 막으면 장애만 키운다."""
    monkeypatch.setattr(rate_limit_module, "get_redis", lambda: _FakeRedis(broken=True))
    client = _client()
    for _ in range(10):
        assert client.post("/try").status_code == 200
