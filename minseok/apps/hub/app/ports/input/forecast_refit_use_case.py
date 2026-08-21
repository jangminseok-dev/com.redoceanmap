from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.forecast_refit_dto import RefitRunOutcome


class ForecastRefitIngestUseCase(ABC):
    """자동화(주 1회 cron)의 가중치 재적합 창구 — 실행 트리거."""

    @abstractmethod
    async def run(self, promote: bool) -> RefitRunOutcome:
        ...
