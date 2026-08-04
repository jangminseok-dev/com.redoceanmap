from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from game.adapter.outbound.pg.community_pg_repository import CommunityPgRepository
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.community_use_case import CommunityUseCase
from game.app.use_cases.community_interactor import CommunityInteractor


def get_community_use_case(db: AsyncSession = Depends(get_db)) -> CommunityUseCase:
    return CommunityInteractor(
        repository=CommunityPgRepository(session=db),
        clock=SystemGameClockAdapter(),
    )
