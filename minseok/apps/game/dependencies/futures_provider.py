from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from game.adapter.outbound.pg.game_account_pg_repository import GameAccountPgRepository
from game.adapter.outbound.pg.game_intervention_pg_repository import (
    GameInterventionPgRepository,
)
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.futures_use_case import FuturesUseCase
from game.app.use_cases.futures_interactor import FuturesInteractor


def get_futures_use_case(db: AsyncSession = Depends(get_db)) -> FuturesUseCase:
    return FuturesInteractor(
        repository=GameAccountPgRepository(session=db),
        clock=SystemGameClockAdapter(),
        interventions=GameInterventionPgRepository(session=db),
    )
