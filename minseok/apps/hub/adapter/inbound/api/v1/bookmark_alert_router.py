"""bookmark_alert_router.py — 외부 자동화(n8n)의 관심 종목 알림 스캔 창구(③-M3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from hub.adapter.inbound.api.schemas.bookmark_alert_schema import (
    AlertEmailSchema,
    BookmarkAlertResponse,
)
from hub.adapter.inbound.api.v1.webhook_token import verify_webhook_token
from hub.app.ports.input.bookmark_alert_use_case import BookmarkAlertUseCase
from hub.dependencies.bookmark_alert_provider import get_bookmark_alert_use_case

bookmark_alert_router = APIRouter(
    prefix="/automation", tags=["automation"],
    dependencies=[Depends(verify_webhook_token)],
)


@bookmark_alert_router.post(
    "/bookmark-alerts", response_model=BookmarkAlertResponse,
    summary="관심 종목(북마크) 신호 알림 스캔 — 발송은 n8n",
)
async def scan_bookmark_alerts(
    use_case: BookmarkAlertUseCase = Depends(get_bookmark_alert_use_case),
) -> BookmarkAlertResponse:
    report = await use_case.scan()
    return BookmarkAlertResponse(
        bookmarksScanned=report.bookmarks_scanned,
        symbolsScanned=report.symbols_scanned,
        signalsFound=report.signals_found,
        deduped=report.deduped,
        emails=[
            AlertEmailSchema(to=e.to, subject=e.subject, body=e.body)
            for e in report.emails
        ],
    )
