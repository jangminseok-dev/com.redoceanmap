from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from game.adapter.outbound.pg.game_account_pg_repository import GameAccountPgRepository
from game.adapter.outbound.pg.game_intervention_pg_repository import (
    GameInterventionPgRepository,
)
from game.adapter.outbound.pg.game_limit_order_pg_repository import (
    GameLimitOrderPgRepository,
)
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.limit_order_use_case import LimitOrderUseCase
from game.app.use_cases.limit_order_interactor import LimitOrderInteractor


def get_limit_order_use_case(db: AsyncSession = Depends(get_db)) -> LimitOrderUseCase:
    return LimitOrderInteractor(
        orders=GameLimitOrderPgRepository(session=db),
        repository=GameAccountPgRepository(session=db),
        clock=SystemGameClockAdapter(),
        interventions=GameInterventionPgRepository(session=db),
    )
