from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from game.adapter.outbound.pg.game_account_pg_repository import GameAccountPgRepository
from game.adapter.outbound.pg.game_store_pg_repository import GameStorePgRepository
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.store_action_use_case import StoreActionUseCase
from game.app.use_cases.store_action_interactor import StoreActionInteractor


def get_store_action_use_case(
    db: AsyncSession = Depends(get_db),
) -> StoreActionUseCase:
    return StoreActionInteractor(
        stores=GameStorePgRepository(session=db),
        accounts=GameAccountPgRepository(session=db),
        clock=SystemGameClockAdapter(),
    )
