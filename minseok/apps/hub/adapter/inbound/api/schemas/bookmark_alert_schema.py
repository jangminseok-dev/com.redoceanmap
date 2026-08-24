from __future__ import annotations

from pydantic import BaseModel


class AlertEmailSchema(BaseModel):
    to: str
    subject: str
    body: str


class TelegramMessageSchema(BaseModel):
    chatId: str
    text: str


class BookmarkAlertResponse(BaseModel):
    """스캔 결과 — n8n이 emails는 Gmail로, telegrams는 텔레그램 봇으로 발송한다."""

    bookmarksScanned: int
    symbolsScanned: int
    signalsFound: int
    deduped: int  # 같은 상태 지속으로 발송을 억제한 쌍 수(종목+상권)
    emails: list[AlertEmailSchema]
    areaBookmarksScanned: int  # 상권 북마크 수(B1)
    areaUpdatesFound: int      # 분기·등급 상태가 확인된 (사용자, 상권) 쌍 수
    telegrams: list[TelegramMessageSchema]  # 텔레그램 발송분(I-7) — 미등록이면 빈 배열
