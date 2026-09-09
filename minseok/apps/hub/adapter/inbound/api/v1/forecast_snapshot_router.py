"""forecast_snapshot_router.py — 수집기(cron)의 예측 스냅샷 캡처·채점 창구."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from hub.adapter.inbound.api.schemas.forecast_snapshot_schema import (
    SnapshotCaptureRequest,
    SnapshotCaptureResponse,
    SnapshotScoreResponse,
)
from hub.adapter.inbound.api.v1.webhook_token import verify_webhook_token
from hub.app.ports.input.forecast_snapshot_use_case import ForecastSnapshotIngestUseCase
from hub.dependencies.forecast_snapshot_provider import get_forecast_snapshot_use_case

forecast_snapshot_router = APIRouter(
    prefix="/automation", tags=["automation"],
    dependencies=[Depends(verify_webhook_token)],
)


@forecast_snapshot_router.post(
    "/forecast-snapshots", response_model=SnapshotCaptureResponse,
    summary="워치리스트 예측 스냅샷 캡처 — 일 1회, 사후 채점용 영속화",
)
async def capture_snapshots(
    payload: SnapshotCaptureRequest,
    use_case: ForecastSnapshotIngestUseCase = Depends(get_forecast_snapshot_use_case),
) -> SnapshotCaptureResponse:
    outcome = await use_case.capture(payload.tickers, payload.horizons)
    return SnapshotCaptureResponse(
        captured=outcome.captured, skipped=outcome.skipped, as_of=outcome.as_of,
    )


@forecast_snapshot_router.post(
    "/forecast-snapshots/score", response_model=SnapshotScoreResponse,
    summary="horizon 도래 스냅샷 채점 — 실현 수익률·적중 기록",
)
async def score_snapshots(
    use_case: ForecastSnapshotIngestUseCase = Depends(get_forecast_snapshot_use_case),
) -> SnapshotScoreResponse:
    outcome = await use_case.score()
    return SnapshotScoreResponse(scored=outcome.scored, pending=outcome.pending)
