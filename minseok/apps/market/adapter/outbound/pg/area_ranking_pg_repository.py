from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.change_indicator_orm import ChangeIndicatorOrm
from market.adapter.outbound.orm.commercial_change_orm import CommercialChangeOrm
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
from market.domain.services.area_scorer import last_four_quarters
from market.domain.value_objects.sales_unit import monthly_from_quarter


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

    async def quarter_range(self) -> tuple[int, int] | None:
        # MIN/MAX가 InitPlan 둘로 갈라져 ix_estimated_sales_year_quarter 양끝을
        # index-only scan한다(43.9만 행에 8버퍼·0.1ms). 새 인덱스가 필요 없다.
        lo, hi = (await self._session.execute(
            select(func.min(EstimatedSalesOrm.year_quarter),
                   func.max(EstimatedSalesOrm.year_quarter))
        )).one()
        return None if lo is None else (int(lo), int(hi))

    async def find_areas(
        self,
        district_name: str | None,
        division_code: str | None,
        dong_name: str | None = None,
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
        if dong_name:
            stmt = stmt.where(dong.name == dong_name)

        rows = (await self._session.execute(stmt)).all()
        out = []
        for ta, div_code, div_name, dong_name, gu_name in rows:
            lat, lng = tm_to_wgs84(ta.x_coord, ta.y_coord)
            out.append(AreaMeta(
                trdar_code=ta.code, trdar_name=ta.name,
                district_name=gu_name or "", dong_name=dong_name or "",
                division_code=div_code, division_name=div_name,
                lat=lat, lng=lng,
                area_size=float(ta.area_size) if ta.area_size is not None else None,
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
            SalesAgg(trdar_code=code, year_quarter=yq, monthly_sales=monthly_from_quarter(int(total or 0)))
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

    async def find_change_indicators(self) -> dict[int, str]:
        latest = (await self._session.execute(
            select(func.max(CommercialChangeOrm.year_quarter))
        )).scalar()
        if latest is None:
            return {}
        rows = (await self._session.execute(
            select(CommercialChangeOrm.trdar_code, ChangeIndicatorOrm.name)
            .join(
                ChangeIndicatorOrm,
                CommercialChangeOrm.change_indicator == ChangeIndicatorOrm.code,
            )
            .where(CommercialChangeOrm.year_quarter == latest)
        )).all()
        return {code: name for code, name in rows}

    async def find_stores(
        self, year_quarter: int, service_code: str | None
    ) -> list[StoreAgg]:
        # 판정용 폐업률 = 최근 4분기 점포 가중(Σ폐업 ÷ Σ점포). 예전 값은 최신 분기 업종별 정수율의 단순평균이라
        # 과반이 0%였고 향후 1년 폐업률 예측력이 절반 이하였다(2026-09-17 점검). 점포 수는 최신 분기 그대로.
        # 점포 수는 유사업종(프랜차이즈 포함) — 원본 점포_수는 프랜차이즈 제외라 매출·폐업과 모수가 어긋난다.
        quarters = last_four_quarters(year_quarter)
        stmt = (
            select(
                StoreOrm.trdar_code,
                func.sum(StoreOrm.similar_industry_store_count).filter(StoreOrm.year_quarter == year_quarter),
                func.sum(StoreOrm.closure_store_count),
                func.sum(StoreOrm.similar_industry_store_count),
                func.count(func.distinct(StoreOrm.year_quarter)),
            )
            .where(StoreOrm.year_quarter.in_(quarters))
            .group_by(StoreOrm.trdar_code)
        )
        if service_code:
            stmt = stmt.where(StoreOrm.service_code == service_code)
        return [
            StoreAgg(
                trdar_code=code,
                store_count=int(latest or 0),
                closure_rate=round(int(closed) * 100 / int(total), 1) if n == 4 and total else None,
            )
            for code, latest, closed, total, n in (await self._session.execute(stmt)).all()
            if latest is not None
        ]
