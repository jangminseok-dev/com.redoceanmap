from __future__ import annotations

from pydantic import BaseModel

from hub.adapter.inbound.api.schemas.bookmark_alert_schema import (
    AlertEmailSchema,
    TelegramMessageSchema,
)


class NewsAlertScanResponse(BaseModel):
    """스캔 결과(B9) — n8n이 emails는 Gmail로, telegrams는 텔레그램 봇으로 발송한다."""

    articlesFound: int      # 커서 이후 임계 통과 뉴스 수
    bookmarksMatched: int   # 북마크와 매칭된 (사용자, 뉴스) 쌍 수
    emails: list[AlertEmailSchema]
    telegrams: list[TelegramMessageSchema]
