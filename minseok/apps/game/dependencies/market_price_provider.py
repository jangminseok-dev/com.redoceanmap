from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from game.adapter.outbound.pg.game_intervention_pg_repository import (
    GameInterventionPgRepository,
)
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.market_price_use_case import MarketPriceUseCase
from game.app.use_cases.market_price_interactor import MarketPriceInteractor


def get_market_price_use_case(db: AsyncSession = Depends(get_db)) -> MarketPriceUseCase:
    """DB 세션이 붙는다 — 시세 자체는 계산이지만 **관리자 개입만은 저장된 값**이라 읽어야 한다."""
    return MarketPriceInteractor(
        clock=SystemGameClockAdapter(),
        interventions=GameInterventionPgRepository(session=db),
    )
