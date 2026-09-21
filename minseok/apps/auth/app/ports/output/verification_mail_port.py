from __future__ import annotations

from abc import ABC, abstractmethod


class VerificationMailPort(ABC):
    """인증 메일 발송 — 지금 구현은 n8n 웹훅(→ Gmail). 발송량이 늘면 이 포트의 어댑터만 바꿔 전용 메일 서비스로 옮긴다."""

    @abstractmethod
    async def send(self, to_email: str, link: str) -> None:
        """실패는 예외로 알린다(호출 측이 사용자에게 재시도를 안내)."""
        ...
