from __future__ import annotations

from pydantic import BaseModel

from hub.adapter.inbound.api.schemas.bookmark_alert_schema import (
    AlertEmailSchema,
    TelegramMessageSchema,
)


class PriceAlertScanResponse(BaseModel):
    """스캔 결과([6]) — n8n이 emails는 Gmail로, telegrams는 텔레그램 봇으로 발송한다."""

    alertsScanned: int
    symbolsScanned: int
    triggered: int  # 도달을 통지하고 비활성화한 조건 수(one-shot)
    emails: list[AlertEmailSchema]
    telegrams: list[TelegramMessageSchema]
