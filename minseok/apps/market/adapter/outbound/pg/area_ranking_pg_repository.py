from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.estimated_sales_orm import EstimatedSalesOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.store_orm import StoreOrm
from market.adapter.outbound.orm.trade_area_division_orm import TradeAreaDivisionOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.adapter.outbound.orm.service_category_orm import ServiceCategoryOrm
from market.app.ports.output.area_ranking_repository import (
    AreaMeta,
    AreaRankingRepositoryPort,
    SalesAgg,
    ServiceRef,
    StoreAgg,
)
from market.utils.coords import tm_to_wgs84


class AreaRankingPgRepository(AreaRankingRepositoryPort):
    """전 상권 집계 — 상권당 쿼리가 아니라 GROUP BY 한 번으로 끝낸다.

    상권 1곳씩 area_score를 부르면 1,650곳 × 6쿼리 ≈ 1만 쿼리가 나온다. 랭킹은
    단일 집계 3개(분기·매출·점포)로 만든다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_quarter(self) -> int | None:
        return (await self._session.execute(
            select(func.max(EstimatedSalesOrm.year_quarter))
        )).scalar()

    async def find_areas(
        self, district_name: str | None, division_code: str | None
    ) -> list[AreaMeta]:
        dong = aliased(RegionOrm)  # 행정동(level2)
        gu = aliased(RegionOrm)    # 자치구(level1)
        stmt = (
            select(TradeAreaOrm, TradeAreaDivisionOrm.code, TradeAreaDivisionOrm.name,
                   dong.name, gu.name)
            .join(TradeAreaDivisionOrm, TradeAreaOrm.division_code == TradeAreaDivisionOrm.code)
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
        )
        if district_name:
            stmt = stmt.where(gu.name == district_name)
        if division_code:
            stmt = stmt.where(TradeAreaOrm.division_code == division_code)

        rows = (await self._session.execute(stmt)).all()
        out = []
        for ta, div_code, div_name, dong_name, gu_name in rows:
            lat, lng = tm_to_wgs84(ta.x_coord, ta.y_coord)
            out.append(AreaMeta(
                trdar_code=ta.code, trdar_name=ta.name,
                district_name=gu_name or "", dong_name=dong_name or "",
                division_code=div_code, division_name=div_name,
                lat=lat, lng=lng,
            ))
        return out

    async def find_sales(
        self, quarters: list[int], service_code: str | None
    ) -> list[SalesAgg]:
        stmt = (
            select(
                EstimatedSalesOrm.trdar_code,
                EstimatedSalesOrm.year_quarter,
                func.sum(EstimatedSalesOrm.monthly_sales_amount),
            )
            .where(EstimatedSalesOrm.year_quarter.in_(quarters))
            .group_by(EstimatedSalesOrm.trdar_code, EstimatedSalesOrm.year_quarter)
        )
        if service_code:
            stmt = stmt.where(EstimatedSalesOrm.service_code == service_code)
        return [
            SalesAgg(trdar_code=code, year_quarter=yq, monthly_sales=int(total or 0))
            for code, yq, total in (await self._session.execute(stmt)).all()
        ]

    async def list_service_codes(self, year_quarter: int) -> list[ServiceRef]:
        rows = (await self._session.execute(
            select(EstimatedSalesOrm.service_code, ServiceCategoryOrm.name)
            .join(ServiceCategoryOrm, EstimatedSalesOrm.service_code == ServiceCategoryOrm.code)
            .where(EstimatedSalesOrm.year_quarter == year_quarter)
            .group_by(EstimatedSalesOrm.service_code, ServiceCategoryOrm.name)
            .order_by(ServiceCategoryOrm.name)
        )).all()
        return [ServiceRef(code=code, name=name) for code, name in rows]

    async def find_stores(
        self, year_quarter: int, service_code: str | None
    ) -> list[StoreAgg]:
        stmt = (
            select(
                StoreOrm.trdar_code,
                func.sum(StoreOrm.store_count),
                func.avg(StoreOrm.closure_rate),
            )
            .where(StoreOrm.year_quarter == year_quarter)
            .group_by(StoreOrm.trdar_code)
        )
        if service_code:
            stmt = stmt.where(StoreOrm.service_code == service_code)
        return [
            StoreAgg(
                trdar_code=code,
                store_count=int(total or 0),
                closure_rate=round(float(rate), 1) if rate is not None else 0.0,
            )
            for code, total, rate in (await self._session.execute(stmt)).all()
        ]
