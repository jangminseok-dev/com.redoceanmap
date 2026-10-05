"""webhook_token.py — /automation/* 라우터 공용 웹훅 토큰 검증 의존성.

외부 자동화(n8n·cron)는 X-Webhook-Token 헤더로 호출자를 검증한다
(N8N_INBOUND_TOKEN env, 비면 검증 생략 — 로컬 개발).
운영(ENV=production)에서 비어 있으면 기동을 거부한다 — 시크릿에서 키 하나가 빠져
/automation/*이 조용히 전부 열리는 것을 막는다. auth 파드는 이 모듈을 import하지 않는다.
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from core.config import ENV, N8N_INBOUND_TOKEN


def require_token_in_production(env: str, token: str | None) -> None:
    if env == "production" and not token:
        raise RuntimeError("N8N_INBOUND_TOKEN 미설정 — 운영에서는 웹훅 검증을 생략할 수 없습니다.")


require_token_in_production(ENV, N8N_INBOUND_TOKEN)


def verify_webhook_token(
    x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token"),
) -> None:
    if not N8N_INBOUND_TOKEN:
        return
    # 상수 시간 비교 — 응답 시간으로 토큰을 한 글자씩 맞혀 가는 타이밍 공격 차단
    if not secrets.compare_digest((x_webhook_token or "").encode(), N8N_INBOUND_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="웹훅 토큰이 올바르지 않습니다.")
