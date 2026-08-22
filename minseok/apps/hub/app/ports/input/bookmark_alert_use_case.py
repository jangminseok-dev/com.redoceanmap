from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.bookmark_alert_dto import BookmarkAlertReport


class BookmarkAlertUseCase(ABC):
    """관심 종목 알림 스캔(③-M3) — 북마크 × 최신 신호 × 회원 이메일 조합."""

    @abstractmethod
    async def scan(self) -> BookmarkAlertReport:
        """전 사용자 종목 북마크를 훑어 비중립 신호를 사용자별 메일로 조립한다(발송은 n8n)."""
        ...
