from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.price_alert_directory_port import PriceAlertDirectoryPort
from recommendation.adapter.outbound.gateways.price_alert_directory_gateway import (
    PriceAlertDirectoryGateway,
)
from recommendation.adapter.outbound.pg.price_alert_pg_repository import (
    PriceAlertPgRepository,
)
from recommendation.app.ports.input.price_alert_use_case import PriceAlertUseCase
from recommendation.app.use_cases.price_alert_interactor import PriceAlertInteractor


def get_price_alert_use_case(
    db: AsyncSession = Depends(get_db),
) -> PriceAlertUseCase:
    return PriceAlertInteractor(alerts=PriceAlertPgRepository(session=db))


def get_price_alert_directory_gateway(
    db: AsyncSession = Depends(get_db),
) -> PriceAlertDirectoryPort:
    """허브 PriceAlertDirectoryPort의 recommendation 구현 — main.py overrides가 주입."""
    return PriceAlertDirectoryGateway(session=db)
