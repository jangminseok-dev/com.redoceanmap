from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.stock_status_port import StockStatusPort
from stock.adapter.outbound.gateways.stock_status_gateway import StockStatusGateway


def get_stock_status_gateway(db: AsyncSession = Depends(get_db)) -> StockStatusPort:
    """허브 StockStatusPort의 stock 구현. main.py가 주입한다."""
    return StockStatusGateway(session=db)
