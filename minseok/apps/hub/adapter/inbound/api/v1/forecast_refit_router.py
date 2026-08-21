"""forecast_refit_router.py — 재적합 배치(주 1회 cron)의 가중치 재적합 창구."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from hub.adapter.inbound.api.schemas.forecast_refit_schema import (
    RefitRunRequest,
    RefitRunResponse,
)
from hub.adapter.inbound.api.v1.webhook_token import verify_webhook_token
from hub.app.ports.input.forecast_refit_use_case import ForecastRefitIngestUseCase
from hub.dependencies.forecast_refit_provider import get_forecast_refit_use_case

forecast_refit_router = APIRouter(
    prefix="/automation", tags=["automation"],
    dependencies=[Depends(verify_webhook_token)],
)


@forecast_refit_router.post(
    "/forecast-refit", response_model=RefitRunResponse,
    summary="판정 가중치 재적합 — 채점 표본 재채점 + 게이트 통과 시 자동 승격",
)
async def run_refit(
    payload: RefitRunRequest,
    use_case: ForecastRefitIngestUseCase = Depends(get_forecast_refit_use_case),
) -> RefitRunResponse:
    outcome = await use_case.run(payload.promote)
    return RefitRunResponse(
        promoted=outcome.promoted,
        activated_key=outcome.activated_key,
        reasons=outcome.reasons,
    )
