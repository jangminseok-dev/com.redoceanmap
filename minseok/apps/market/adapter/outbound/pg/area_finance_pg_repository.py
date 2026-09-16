from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.interest_rate_orm import InterestRateOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.rent_benchmark_orm import RentBenchmarkOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.app.ports.output.area_finance_repository import AreaFinanceRepositoryPort
from market.domain.services.rent_matcher import match_area, zone_for
from market.domain.value_objects.finance_vo import RentBenchmark

_BUILDING = "small"
_CITY = "서울"


class AreaFinancePgRepository(AreaFinanceRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _latest(self, level: int, region_name: str) -> RentBenchmarkOrm | None:
        return (await self._session.execute(
            select(RentBenchmarkOrm)
            .where(RentBenchmarkOrm.building_type == _BUILDING, RentBenchmarkOrm.level == level,
                   RentBenchmarkOrm.region_name == region_name)
            .order_by(RentBenchmarkOrm.year_quarter.desc()).limit(1)
        )).scalar_one_or_none()

    async def find_rent(self, trdar_code: int) -> RentBenchmark | None:
        dong, gu = aliased(RegionOrm), aliased(RegionOrm)
        row = (await self._session.execute(
            select(TradeAreaOrm.name, gu.name)
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
            .where(TradeAreaOrm.code == trdar_code)
        )).first()
        if row is None:
            return None
        name, district = row[0], row[1] or ""
        candidates = []
        area = match_area(name, district)
        if area:
            candidates.append((2, area, "area"))
        candidates.append((1, zone_for(district), "zone"))
        candidates.append((0, _CITY, "city"))
        for level, region, tag in candidates:
            r = await self._latest(level, region)
            if r is not None:
                return RentBenchmark(year_quarter=r.year_quarter, rent_per_sqm_krw=r.rent_per_sqm_krw,
                                     vacancy_rate=r.vacancy_rate, region_name=r.region_name, level=tag)
        return None

    async def find_loan_rate(self) -> tuple[int, float] | None:
        r = (await self._session.execute(
            select(InterestRateOrm.year_month, InterestRateOrm.rate)
            .where(InterestRateOrm.stat_code == "121Y006", InterestRateOrm.item_name == "대출평균")
            .order_by(InterestRateOrm.year_month.desc()).limit(1)
        )).first()
        return (int(r[0]), float(r[1])) if r else None
