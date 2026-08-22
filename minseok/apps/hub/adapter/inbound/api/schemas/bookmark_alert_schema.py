from __future__ import annotations

from pydantic import BaseModel


class AlertEmailSchema(BaseModel):
    to: str
    subject: str
    body: str


class BookmarkAlertResponse(BaseModel):
    """스캔 결과 — n8n이 emails를 순회하며 Gmail 발송한다."""

    bookmarksScanned: int
    symbolsScanned: int
    signalsFound: int
    emails: list[AlertEmailSchema]
