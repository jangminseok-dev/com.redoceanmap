from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_market_db
from hub.app.ports.output.area_finance_port import AreaFinancePort
from market.adapter.outbound.gateways.area_finance_gateway import AreaFinanceGateway
from market.adapter.outbound.pg.area_detail_pg_repository import AreaDetailPgRepository
from market.adapter.outbound.pg.area_finance_pg_repository import AreaFinancePgRepository
from market.app.ports.input.area_finance_use_case import AreaFinanceUseCase
from market.app.use_cases.area_finance_interactor import AreaFinanceInteractor


def get_area_finance_use_case(db: AsyncSession = Depends(get_market_db)) -> AreaFinanceUseCase:
    return AreaFinanceInteractor(
        finance=AreaFinancePgRepository(session=db), detail=AreaDetailPgRepository(session=db),
    )


def get_area_finance_gateway(db: AsyncSession = Depends(get_market_db)) -> AreaFinancePort:
    """허브 AreaFinancePort 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    return AreaFinanceGateway(use_case=get_area_finance_use_case(db))
