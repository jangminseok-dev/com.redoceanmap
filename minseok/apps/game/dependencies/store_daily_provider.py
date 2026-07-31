from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from game.adapter.outbound.pg.game_store_pg_repository import GameStorePgRepository
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.store_daily_use_case import StoreDailyUseCase
from game.app.use_cases.store_daily_interactor import StoreDailyInteractor


def get_store_daily_use_case(db: AsyncSession = Depends(get_db)) -> StoreDailyUseCase:
    return StoreDailyInteractor(
        stores=GameStorePgRepository(session=db),
        clock=SystemGameClockAdapter(),
    )
