from __future__ import annotations

import logging

from redis.asyncio import Redis

from core.config import REDIS_URL, REDIS_URL_MOBILE

logger = logging.getLogger("uvicorn.error")

_client: Redis | None = None
_mobile_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def get_redis_mobile() -> Redis:
    """모바일 세션 전용 클라이언트(논리 db 1).

    하나의 클라이언트에서 SELECT로 DB를 오가지 않는다 — 커넥션 풀에 DB 상태가 남아
    웹 세션 키를 모바일 DB에 쓰는 사고가 난다. 접속을 아예 둘로 나눈다.
    """
    global _mobile_client
    if _mobile_client is None:
        _mobile_client = Redis.from_url(REDIS_URL_MOBILE, decode_responses=True)
    return _mobile_client


async def ping() -> bool:
    """Redis가 살아 있는지 본다 (/health 전용). 원인은 응답에 싣지 않는다 — 공개 엔드포인트."""
    try:
        return bool(await get_redis().ping())
    except Exception:
        logger.exception("Redis 헬스체크 실패")
        return False


async def dispose_redis() -> None:
    global _client, _mobile_client
    if _client is not None:
        await _client.aclose()
    if _mobile_client is not None:
        await _mobile_client.aclose()
    _client = None
    _mobile_client = None
