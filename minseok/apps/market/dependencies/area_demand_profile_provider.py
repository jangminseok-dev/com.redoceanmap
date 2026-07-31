from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_market_db
from hub.app.ports.output.area_demand_profile_port import AreaDemandProfilePort
from market.adapter.outbound.gateways.area_demand_profile_gateway import (
    AreaDemandProfileGateway,
)


def get_area_demand_profile_gateway(
    db: AsyncSession = Depends(get_market_db),
) -> AreaDemandProfilePort:
    return AreaDemandProfileGateway(session=db)
