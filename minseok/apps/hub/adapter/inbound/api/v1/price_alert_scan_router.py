"""price_alert_scan_router.py — 외부 자동화(n8n)의 가격 도달 알림 스캔 창구([6])."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from hub.adapter.inbound.api.schemas.bookmark_alert_schema import (
    AlertEmailSchema,
    TelegramMessageSchema,
)
from hub.adapter.inbound.api.schemas.price_alert_scan_schema import PriceAlertScanResponse
from hub.adapter.inbound.api.v1.webhook_token import verify_webhook_token
from hub.app.ports.input.price_alert_scan_use_case import PriceAlertScanUseCase
from hub.dependencies.price_alert_scan_provider import get_price_alert_scan_use_case

price_alert_scan_router = APIRouter(
    prefix="/automation", tags=["automation"],
    dependencies=[Depends(verify_webhook_token)],
)


@price_alert_scan_router.post(
    "/price-alerts", response_model=PriceAlertScanResponse,
    summary="가격 도달 알림 스캔(사용자 설정 조건) — 발송은 n8n",
)
async def scan_price_alerts(
    use_case: PriceAlertScanUseCase = Depends(get_price_alert_scan_use_case),
) -> PriceAlertScanResponse:
    report = await use_case.scan()
    return PriceAlertScanResponse(
        alertsScanned=report.alerts_scanned,
        symbolsScanned=report.symbols_scanned,
        triggered=report.triggered,
        emails=[
            AlertEmailSchema(to=e.to, subject=e.subject, body=e.body)
            for e in report.emails
        ],
        telegrams=[
            TelegramMessageSchema(chatId=m.chat_id, text=m.text)
            for m in report.telegrams
        ],
    )
