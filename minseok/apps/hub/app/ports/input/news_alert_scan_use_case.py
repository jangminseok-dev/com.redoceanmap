from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.news_alert_dto import NewsAlertScanReport


class NewsAlertScanUseCase(ABC):
    """티커 뉴스 알림 스캔 유스케이스(B9) — n8n 자동화 창구가 트리거한다."""

    @abstractmethod
    async def scan(self) -> NewsAlertScanReport:
        ...
