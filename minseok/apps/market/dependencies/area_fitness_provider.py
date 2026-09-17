from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_market_db
from market.adapter.outbound.pg.area_demand_profile_pg_repository import (
    AreaDemandProfilePgRepository,
)
from market.app.ports.input.area_fitness_use_case import AreaFitnessUseCase
from market.app.use_cases.area_fitness_interactor import AreaFitnessInteractor


def get_area_fitness_use_case(db: AsyncSession = Depends(get_market_db)) -> AreaFitnessUseCase:
    return AreaFitnessInteractor(profiles=AreaDemandProfilePgRepository(session=db))


def get_area_fitness_gateway(db: AsyncSession = Depends(get_market_db)):
    """허브 AreaFitnessPort 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    from market.adapter.outbound.gateways.area_fitness_gateway import AreaFitnessGateway

    return AreaFitnessGateway(use_case=get_area_fitness_use_case(db))
