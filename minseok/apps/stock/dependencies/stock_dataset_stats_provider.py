from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.stock_dataset_stats_port import StockDatasetStatsPort
from stock.adapter.outbound.gateways.stock_dataset_stats_gateway import (
    StockDatasetStatsGateway,
)


def get_stock_dataset_stats_gateway(
    db: AsyncSession = Depends(get_db),
) -> StockDatasetStatsPort:
    """허브 StockDatasetStatsPort 구현 프로바이더 — main.py가 dependency_overrides로 주입."""
    return StockDatasetStatsGateway(session=db)
