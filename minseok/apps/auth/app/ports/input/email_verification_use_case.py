from __future__ import annotations

from abc import ABC, abstractmethod

from auth.app.dtos.email_verification_dto import VerifyRequestOutcome


class EmailVerificationUseCase(ABC):
    """이메일 인증 — 알림 메일 수신 조건. 가입·로그인의 관문이 아니다."""

    @abstractmethod
    async def request(self, user_id: int) -> VerifyRequestOutcome:
        """로그인한 본인 주소로 인증 메일을 보낸다. 발송 실패는 예외."""
        ...

    @abstractmethod
    async def confirm(self, token: str) -> bool:
        """링크의 토큰을 확인해 인증을 기록한다. 없는·만료된·이미 쓴 토큰이면 False."""
        ...
