from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from game.adapter.outbound.pg.game_account_pg_repository import GameAccountPgRepository
from game.adapter.outbound.pg.game_store_pg_repository import GameStorePgRepository
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.store_open_use_case import StoreOpenUseCase
from game.app.use_cases.store_open_interactor import StoreOpenInteractor
from hub.app.ports.output.area_demand_profile_port import AreaDemandProfilePort
from hub.dependencies.area_demand_profile_provider import get_area_demand_profile_port


def get_store_open_use_case(
    db: AsyncSession = Depends(get_db),
    profiles: AreaDemandProfilePort = Depends(get_area_demand_profile_port),
) -> StoreOpenUseCase:
    return StoreOpenInteractor(
        profiles=profiles,
        stores=GameStorePgRepository(session=db),
        accounts=GameAccountPgRepository(session=db),
        clock=SystemGameClockAdapter(),
    )
