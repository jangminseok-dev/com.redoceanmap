from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_market_db
from market.adapter.outbound.pg.area_ranking_pg_repository import AreaRankingPgRepository
from market.app.ports.input.area_ranking_use_case import AreaRankingUseCase
from market.app.use_cases.area_ranking_interactor import AreaRankingInteractor


def get_area_ranking_use_case(db: AsyncSession = Depends(get_market_db)) -> AreaRankingUseCase:
    return AreaRankingInteractor(repo=AreaRankingPgRepository(session=db))
