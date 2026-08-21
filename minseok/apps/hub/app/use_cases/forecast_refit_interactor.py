from __future__ import annotations

import logging

from hub.app.dtos.forecast_refit_dto import RefitRunOutcome
from hub.app.ports.input.forecast_refit_use_case import ForecastRefitIngestUseCase
from hub.app.ports.output.forecast_refit_port import ForecastRefitPort

logger = logging.getLogger(__name__)


class ForecastRefitInteractor(ForecastRefitIngestUseCase):
    """가중치 재적합 허브 대장 — 스포크 구현(포트)에 위임하고 결과를 기록한다."""

    def __init__(self, refits: ForecastRefitPort) -> None:
        self._refits = refits

    async def run(self, promote: bool) -> RefitRunOutcome:
        outcome = await self._refits.run(promote)
        logger.info(
            "[hub-forecast-refit] promote=%s → 승격 %s(%s) 사유 %s",
            promote, outcome.promoted, outcome.activated_key, "; ".join(outcome.reasons),
        )
        return outcome
