"""요청 빈도 제한 — Redis 고정 윈도우 카운터.

인증 엔드포인트(로그인·가입·재발급)의 무차별 대입·크리덴셜 스터핑을 막는다.
저장소는 이미 리프레시 토큰이 쓰고 있는 Redis를 그대로 재사용한다(새 의존성 없음).
JWT 검증과 달리 인증 '전' 단계라 core에 두고 auth 라우터가 의존성으로 건다.
"""
from __future__ import annotations

import logging
import time

from fastapi import Depends, HTTPException, Request, status
from redis.exceptions import RedisError

from core.redis import get_redis

logger = logging.getLogger("uvicorn.error")


def _client_ip(request: Request) -> str:
    """실 클라이언트 IP — cloudflared가 붙이는 헤더 우선.

    백엔드 포트는 루프백 바인딩이라 외부 유입은 터널뿐이고, 터널은 이 헤더를 자기가 덮어쓴다.
    따라서 헤더 위조로 제한을 우회할 수 없다(포트가 열려 있다면 성립하지 않는 전제).
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, limit: int, window_seconds: int):
    """IP 단위 고정 윈도우 제한 의존성 팩토리 — 초과 시 429(Retry-After).

    윈도우 경계에서 최대 2배까지 통과할 수 있다(고정 윈도우의 알려진 성질).
    무차별 대입 저지에는 충분하고, 슬라이딩 윈도우의 복잡도를 사지 않는다.
    """

    async def _dep(request: Request) -> None:
        now = int(time.time())
        window = now // window_seconds
        key = f"ratelimit:{bucket}:{window}:{_client_ip(request)}"
        redis = get_redis()
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window_seconds)
        except RedisError as e:
            # 열림 정책(fail-open): auth는 이미 Redis에 강하게 의존한다(리프레시 저장소).
            # Redis가 죽으면 로그인·재발급 자체가 실패하므로, 여기서 추가로 막아 얻을 게 없다.
            logger.warning("[rate_limit] Redis 사용 불가 — 제한 생략(%s): %s", bucket, e)
            return
        if count > limit:
            retry_after = (window + 1) * window_seconds - now
            logger.warning("[rate_limit] %s 초과 — key=%s count=%s", bucket, key, count)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"요청이 너무 잦습니다. {retry_after}초 뒤 다시 시도해 주세요.",
                headers={"Retry-After": str(retry_after)},
            )

    return Depends(_dep)
