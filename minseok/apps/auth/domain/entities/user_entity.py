from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class User:
    """사용자 도메인 엔티티 — ORM/프레임워크에 의존하지 않는다."""

    id: int
    email: str | None  # 카카오 로그인은 이메일 동의가 선택이라 없을 수 있다
    password_hash: str
    name: str
    kakao_id: int | None = None  # 카카오 회원번호 — 모바일 로그인의 식별자
    last_login_at: datetime | None = None
    terms_agreed_at: datetime | None = None  # 필수 약관 동의 시각 (구 유저는 None)
    marketing_agreed: bool = False
    suspended_at: datetime | None = None  # 운영자 정지 시각 (None = 정상, 해제 가능)
    suspended_reason: str | None = None
    deleted_at: datetime | None = None  # 탈퇴 처리 시각 — 개인정보 익명화 동반, 비가역
    email_verified_at: datetime | None = None  # 이메일 인증 시각 (None = 미인증 — 알림 메일 미발송)

    def ensure_active(self) -> None:
        """정지/탈퇴 계정이면 ValueError — 로그인·소셜·리프레시 공통 관문."""
        if self.deleted_at is not None:
            raise ValueError("탈퇴한 계정입니다.")
        if self.suspended_at is not None:
            raise ValueError("정지된 계정입니다. 관리자에게 문의해 주세요.")
