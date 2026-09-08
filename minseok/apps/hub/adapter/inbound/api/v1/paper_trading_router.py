"""paper_trading_router.py — cron·리플레이의 모의투자 step 창구."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from hub.adapter.inbound.api.schemas.paper_trading_schema import PaperStepRequest, PaperStepResponse
from hub.adapter.inbound.api.v1.webhook_token import verify_webhook_token
from hub.app.ports.output.paper_trading_port import PaperTradingPort
from hub.dependencies.paper_trading_provider import get_paper_trading_port

paper_trading_router = APIRouter(
    prefix="/automation", tags=["automation"], dependencies=[Depends(verify_webhook_token)],
)


@paper_trading_router.post(
    "/paper/step", response_model=PaperStepResponse,
    summary="모의투자 일일 step — 체결·평가·채점·판단(멱등)",
)
async def paper_step(
    payload: PaperStepRequest,
    port: PaperTradingPort = Depends(get_paper_trading_port),
) -> PaperStepResponse:
    as_of = payload.as_of or datetime.now(UTC)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    out = await port.step(as_of, payload.replay)
    return PaperStepResponse(**out.__dict__)
