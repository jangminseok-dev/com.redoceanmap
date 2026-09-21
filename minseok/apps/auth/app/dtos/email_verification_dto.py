from __future__ import annotations

from enum import Enum


class VerifyRequestOutcome(str, Enum):
    """인증 메일 요청의 결과 — 라우터가 상태 코드와 안내 문구로 옮긴다."""

    SENT = "sent"
    ALREADY_VERIFIED = "already_verified"
    NO_EMAIL = "no_email"                # 이메일 없이 가입한 계정(일부 소셜)
    UNDELIVERABLE = "undeliverable"      # 메일을 받을 수 없는 주소(테스트·예약 도메인) — 보내지 않는다
    THROTTLED = "throttled"              # 재요청 간격·하루 한도
