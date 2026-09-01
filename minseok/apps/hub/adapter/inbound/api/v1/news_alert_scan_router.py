"""news_alert_scan_router.py — 외부 자동화(n8n)의 티커 뉴스 알림 스캔 창구(B9)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from hub.adapter.inbound.api.schemas.bookmark_alert_schema import (
    AlertEmailSchema,
    TelegramMessageSchema,
)
from hub.adapter.inbound.api.schemas.news_alert_scan_schema import NewsAlertScanResponse
from hub.adapter.inbound.api.v1.webhook_token import verify_webhook_token
from hub.app.ports.input.news_alert_scan_use_case import NewsAlertScanUseCase
from hub.dependencies.news_alert_scan_provider import get_news_alert_scan_use_case

news_alert_scan_router = APIRouter(
    prefix="/automation", tags=["automation"],
    dependencies=[Depends(verify_webhook_token)],
)


@news_alert_scan_router.post(
    "/news-alerts", response_model=NewsAlertScanResponse,
    summary="관심 종목 강한 감성 뉴스 알림 스캔(B9) — 발송은 n8n",
)
async def scan_news_alerts(
    use_case: NewsAlertScanUseCase = Depends(get_news_alert_scan_use_case),
) -> NewsAlertScanResponse:
    report = await use_case.scan()
    return NewsAlertScanResponse(
        articlesFound=report.articles_found,
        bookmarksMatched=report.bookmarks_matched,
        emails=[
            AlertEmailSchema(to=e.to, subject=e.subject, body=e.body)
            for e in report.emails
        ],
        telegrams=[
            TelegramMessageSchema(chatId=m.chat_id, text=m.text)
            for m in report.telegrams
        ],
    )
