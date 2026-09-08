from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.change_indicator_orm import ChangeIndicatorOrm
from market.adapter.outbound.orm.commercial_change_benchmark_orm import (
    CommercialChangeBenchmarkOrm,
)
from market.adapter.outbound.orm.commercial_change_orm import CommercialChangeOrm
from market.adapter.outbound.orm.estimated_sales_orm import EstimatedSalesOrm
from market.adapter.outbound.orm.floating_population_orm import FloatingPopulationOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.service_category_orm import ServiceCategoryOrm
from market.adapter.outbound.orm.store_orm import StoreOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.app.dtos.area_stats_dto import (
    AreaHeader,
    ChangeSummary,
    FloatingQuarter,
    SalesQuarter,
    ServiceRef,
    StoreQuarter,
)
from market.app.ports.output.area_stats_repository import AreaStatsRepositoryPort
from market.domain.value_objects.sales_unit import monthly_from_quarter


class AreaStatsPgRepository(AreaStatsRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_header(self, trdar_code: int) -> AreaHeader | None:
        dong = aliased(RegionOrm)  # 행정동(level2)
        gu = aliased(RegionOrm)    # 자치구(level1)
        row = (await self._session.execute(
            select(TradeAreaOrm.code, TradeAreaOrm.name, gu.name)
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
            .where(TradeAreaOrm.code == trdar_code)
        )).first()
        if row is None:
            return None
        code, name, gu_name = row
        return AreaHeader(trdar_code=code, trdar_name=name, district_name=gu_name or "")

    async def resolve_service(self, trdar_code: int, service_code: str | None) -> ServiceRef | None:
        if service_code is None:
            latest_quarter = (await self._session.execute(
                select(func.max(EstimatedSalesOrm.year_quarter))
                .where(EstimatedSalesOrm.trdar_code == trdar_code)
            )).scalar()
            if latest_quarter is None:
                return None
            service_code = (await self._session.execute(
                select(EstimatedSalesOrm.service_code)
                .where(
                    EstimatedSalesOrm.trdar_code == trdar_code,
                    EstimatedSalesOrm.year_quarter == latest_quarter,
                )
                .order_by(EstimatedSalesOrm.monthly_sales_amount.desc())
                .limit(1)
            )).scalar()
        name = (await self._session.execute(
            select(ServiceCategoryOrm.name).where(ServiceCategoryOrm.code == service_code)
        )).scalar()
        if name is None:
            return None
        return ServiceRef(code=service_code, name=name)

    async def find_sales(
        self, trdar_code: int, service_code: str, quarters: int
    ) -> list[SalesQuarter]:
        rows = (await self._session.execute(
            select(EstimatedSalesOrm)
            .where(
                EstimatedSalesOrm.trdar_code == trdar_code,
                EstimatedSalesOrm.service_code == service_code,
            )
            .order_by(EstimatedSalesOrm.year_quarter.desc())
            .limit(quarters)
        )).scalars().all()
        return [
            SalesQuarter(
                year_quarter=r.year_quarter,
                # 원본은 분기 합계 — 월 이름으로 내보내는 경계에서 ÷3 (sales_unit 참고)
                monthly_sales_amount=monthly_from_quarter(r.monthly_sales_amount),
                weekday_sales_amount=monthly_from_quarter(r.weekday_sales_amount),
            )
            for r in reversed(rows)
        ]

    async def find_stores(
        self, trdar_code: int, service_code: str, quarters: int
    ) -> list[StoreQuarter]:
        rows = (await self._session.execute(
            select(StoreOrm)
            .where(StoreOrm.trdar_code == trdar_code, StoreOrm.service_code == service_code)
            .order_by(StoreOrm.year_quarter.desc())
            .limit(quarters)
        )).scalars().all()
        return [
            StoreQuarter(
                year_quarter=r.year_quarter,
                store_count=r.store_count,
                opening_rate=r.opening_rate,
                closure_rate=r.closure_rate,
                franchise_store_count=r.franchise_store_count,
                similar_industry_store_count=r.similar_industry_store_count,
                opening_store_count=r.opening_store_count,
                closure_store_count=r.closure_store_count,
            )
            for r in reversed(rows)
        ]

    async def find_floating(self, trdar_code: int, quarters: int) -> list[FloatingQuarter]:
        rows = (await self._session.execute(
            select(FloatingPopulationOrm)
            .where(FloatingPopulationOrm.trdar_code == trdar_code)
            .order_by(FloatingPopulationOrm.year_quarter.desc())
            .limit(quarters)
        )).scalars().all()
        return [
            FloatingQuarter(
                year_quarter=r.year_quarter,
                total=r.total_floating_pop,
                age_10=r.age_10_floating_pop,
                age_20=r.age_20_floating_pop,
                age_30=r.age_30_floating_pop,
                age_40=r.age_40_floating_pop,
                age_50=r.age_50_floating_pop,
                age_60_plus=r.age_60_plus_floating_pop,
                time_00_06=r.time_00_06_floating_pop,
                time_06_11=r.time_06_11_floating_pop,
                time_11_14=r.time_11_14_floating_pop,
                time_14_17=r.time_14_17_floating_pop,
                time_17_21=r.time_17_21_floating_pop,
                time_21_24=r.time_21_24_floating_pop,
            )
            for r in reversed(rows)
        ]

    async def find_change(self, trdar_code: int) -> ChangeSummary | None:
        row = (await self._session.execute(
            select(CommercialChangeOrm, ChangeIndicatorOrm.name)
            .outerjoin(
                ChangeIndicatorOrm,
                CommercialChangeOrm.change_indicator == ChangeIndicatorOrm.code,
            )
            .where(CommercialChangeOrm.trdar_code == trdar_code)
            .order_by(CommercialChangeOrm.year_quarter.desc())
            .limit(1)
        )).first()
        if row is None:
            return None
        cc, indicator_name = row

        # 상권 → 시도 코드 해소 후 같은 분기의 지역 벤치마크 매핑(CommercialDataGateway와 동일 규칙)
        dong = aliased(RegionOrm)
        gu = aliased(RegionOrm)
        sido_code = (await self._session.execute(
            select(gu.parent_code)
            .select_from(TradeAreaOrm)
            .join(dong, TradeAreaOrm.region_code == dong.code)
            .join(gu, dong.parent_code == gu.code)
            .where(TradeAreaOrm.code == trdar_code)
        )).scalar()
        region_avg = None
        if sido_code:
            region_avg = (await self._session.execute(
                select(
                    CommercialChangeBenchmarkOrm.operating_months_avg,
                    CommercialChangeBenchmarkOrm.closure_months_avg,
                ).where(
                    CommercialChangeBenchmarkOrm.region_code == sido_code,
                    CommercialChangeBenchmarkOrm.year_quarter == cc.year_quarter,
                )
            )).first()

        return ChangeSummary(
            change_indicator_name=indicator_name,
            operating_months_avg=cc.operating_months_avg,
            region_operating_months_avg=region_avg[0] if region_avg else None,
            closure_months_avg=cc.closure_months_avg,
            region_closure_months_avg=region_avg[1] if region_avg else None,
        )
