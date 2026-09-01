"""티커 뉴스 알림 계약 DTO(B9) — 허브 스캔(소비)과 stock(구현)을 잇는다."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from hub.app.dtos.bookmark_alert_dto import AlertEmail, TelegramMessage


@dataclass(frozen=True)
class AlertableNews:
    """알림 후보 뉴스 1건 — 커서 이후 적재된 강한 감성(|sentiment|≥임계) 라벨만."""

    news_id: int
    ticker: str
    title: str
    sentiment: float
    event_type: str | None
    published_at: datetime | None


@dataclass(frozen=True)
class NewsAlertScanReport:
    articles_found: int          # 커서 이후 임계 통과 뉴스 수
    bookmarks_matched: int       # 북마크와 매칭된 (사용자, 뉴스) 쌍 수
    emails: list[AlertEmail] = field(default_factory=list)
    telegrams: list[TelegramMessage] = field(default_factory=list)
