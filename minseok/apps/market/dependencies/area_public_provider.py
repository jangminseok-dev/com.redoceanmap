from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_market_db
from market.adapter.outbound.pg.area_detail_pg_repository import AreaDetailPgRepository
from market.adapter.outbound.pg.area_index_pg_repository import AreaIndexPgRepository
from market.adapter.outbound.pg.area_score_pg_repository import AreaScorePgRepository
from market.app.ports.input.area_public_use_case import AreaPublicUseCase
from market.app.use_cases.area_detail_interactor import AreaDetailInteractor
from market.app.use_cases.area_public_interactor import AreaPublicInteractor
from market.app.use_cases.area_score_interactor import AreaScoreInteractor


def get_area_public_use_case(db: AsyncSession = Depends(get_market_db)) -> AreaPublicUseCase:
    return AreaPublicInteractor(
        index=AreaIndexPgRepository(session=db),
        detail=AreaDetailInteractor(detail=AreaDetailPgRepository(session=db)),
        score=AreaScoreInteractor(repo=AreaScorePgRepository(session=db)),
    )
