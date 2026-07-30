from __future__ import annotations

import logging

from redis.asyncio import Redis

from core.config import REDIS_URL

logger = logging.getLogger("uvicorn.error")

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(REDIS_URL, decode_responses=True)
    return _client


async def ping() -> bool:
    """Redis가 살아 있는지 본다 (/health 전용). 원인은 응답에 싣지 않는다 — 공개 엔드포인트."""
    try:
        return bool(await get_redis().ping())
    except Exception:
        logger.exception("Redis 헬스체크 실패")
        return False


async def dispose_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None
