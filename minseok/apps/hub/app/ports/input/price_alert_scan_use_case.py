from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.price_alert_scan_dto import PriceAlertScanReport


class PriceAlertScanUseCase(ABC):
    """가격 도달 스캔 유스케이스([6]) — n8n 자동화 창구가 트리거한다."""

    @abstractmethod
    async def scan(self) -> PriceAlertScanReport:
        ...
