"""이메일 인증 규칙 — 토큰·수명·요청 제한(순수, 2026-09-21).

인증은 **알림 메일 수신 조건**일 뿐 가입·로그인의 관문이 아니다. 인증 메일은 n8n → Gmail로 나가는데 그 연결은 끊긴 적이 있다
(2026-09 초) — 관문으로 두면 그날은 아무도 가입하지 못한다. 그리고 인증 메일 자체가 "아직 확인 안 된 주소로 가는 메일"이라
요청 횟수를 묶는다(남의 주소로 가입해 인증 메일을 반복 요청하는 것을 막는다).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

TOKEN_TTL = timedelta(hours=24)        # 링크 유효 시간
REQUEST_COOLDOWN = timedelta(minutes=5)  # 같은 계정의 재요청 간격
DAILY_REQUEST_LIMIT = 3                # 같은 계정의 하루 요청 수


def new_token() -> str:
    """추측 불가능한 1회용 토큰(URL 안전) — 메일 링크에만 실리고 서버에는 해시만 남는다."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """저장 키 — 저장소가 털려도 살아 있는 링크를 만들 수 없게 원문을 보관하지 않는다."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_link(site_url: str, token: str) -> str:
    return f"{site_url.rstrip('/')}/verify-email?token={token}"
