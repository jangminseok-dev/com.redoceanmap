from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.commercial_change_benchmark_orm import (
    CommercialChangeBenchmarkOrm,
)
from market.adapter.outbound.orm.commercial_change_orm import CommercialChangeOrm
from market.adapter.outbound.orm.estimated_sales_orm import EstimatedSalesOrm
from market.adapter.outbound.orm.floating_population_orm import FloatingPopulationOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.store_orm import StoreOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.app.dtos.area_score_dto import (
    AreaScoreHeader,
    PersistenceStat,
    StoreHealthStat,
)
from market.app.ports.output.area_score_repository import AreaScoreRepositoryPort
from market.domain.services.area_scorer import MAX_QUARTERS
from market.domain.value_objects.area_score_vo import QuarterValue
from market.domain.value_objects.sales_unit import monthly_from_quarter


def _sido_join(stmt, fact_orm):
    """팩트 → trade_area → 행정동 → 자치구 조인 (시도 필터는 gu.parent_code)."""
    dong = aliased(RegionOrm)
    gu = aliased(RegionOrm)
    return (
        stmt.join(TradeAreaOrm, fact_orm.trdar_code == TradeAreaOrm.code)
        .join(dong, TradeAreaOrm.region_code == dong.code)
        .join(gu, dong.parent_code == gu.code)
    ), gu


# 시도 벤치마크는 **상권과 무관하게 같은 값**인데 `/score` 요청마다 재집계됐다.
# 실측: 매출 시리즈 1회가 55,977 버퍼(≈437MB)를 읽고 5행을 낸다 — 2021~2024 백필로
# 43.9만 행이 되면서 백필 전 대비 약 20배 느려졌고, 분기를 더 넣을수록 악화된다.
#
# 무효화는 해당 팩트의 최신 분기를 버전 키로 삼는다(index-only scan, 4버퍼·0.08ms).
# 분기 적재가 들어오면 키가 바뀌어 자연 갱신된다 — stock_forecast가 마지막 봉 ts를
# 캐시 키로 쓰는 것과 같은 방식. 분기 데이터는 분기당 1회만 바뀌므로 TTL은 불필요하고,
# 값이 작고 무효화 키가 명확해 Redis도 과설계다.
_CITY_CACHE: dict[tuple, tuple[int, object]] = {}


class AreaScorePgRepository(AreaScoreRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _latest_quarter(self, fact_orm) -> int | None:
        """팩트의 최신 분기 — 벤치마크 캐시의 버전 키(index-only scan)."""
        return (await self._session.execute(
            select(func.max(fact_orm.year_quarter))
        )).scalar()

    async def _cached_city(self, key: tuple, fact_orm, compute):
        """시도 벤치마크 캐시 — 최신 분기가 그대로면 재집계하지 않는다."""
        version = await self._latest_quarter(fact_orm)
        hit = _CITY_CACHE.get(key)
        if hit is not None and hit[0] == version:
            return hit[1]
        value = await compute()
        if version is not None:
            _CITY_CACHE[key] = (version, value)
        return value

    async def find_header(self, trdar_code: int) -> AreaScoreHeader | None:
        dong = aliased(RegionOrm)
        gu = aliased(RegionOrm)
        row = (await self._session.execute(
            select(TradeAreaOrm.code, TradeAreaOrm.name, gu.name, gu.parent_code)
            .outerjoin(dong, TradeAreaOrm.region_code == dong.code)
            .outerjoin(gu, dong.parent_code == gu.code)
            .where(TradeAreaOrm.code == trdar_code)
        )).first()
        if row is None:
            return None
        code, name, gu_name, sido_code = row
        return AreaScoreHeader(
            trdar_code=code, trdar_name=name,
            district_name=gu_name or "", sido_code=sido_code,
        )

    async def find_sales_series(self, trdar_code: int, quarters: int) -> list[QuarterValue]:
        rows = (await self._session.execute(
            select(
                EstimatedSalesOrm.year_quarter,
                func.sum(EstimatedSalesOrm.monthly_sales_amount),
            )
            .where(EstimatedSalesOrm.trdar_code == trdar_code)
            .group_by(EstimatedSalesOrm.year_quarter)
            .order_by(EstimatedSalesOrm.year_quarter.desc())
            .limit(quarters)
        )).all()
        # 화면 trend.monthlySales로 나가는 절대값 — 분기 합계를 월로 환산(성장률은 비율이라 불변)
        return [
            QuarterValue(year_quarter=yq, value=float(monthly_from_quarter(total)))
            for yq, total in reversed(rows)
        ]

    async def find_floating_series(self, trdar_code: int, quarters: int) -> list[QuarterValue]:
        rows = (await self._session.execute(
            select(FloatingPopulationOrm.year_quarter, FloatingPopulationOrm.total_floating_pop)
            .where(FloatingPopulationOrm.trdar_code == trdar_code)
            .order_by(FloatingPopulationOrm.year_quarter.desc())
            .limit(quarters)
        )).all()
        return [QuarterValue(year_quarter=yq, value=float(total)) for yq, total in reversed(rows)]

    async def _city_series(
        self, key: str, sido_code: str, fact_orm, value_col
    ) -> list[QuarterValue]:
        """시도 합계 시리즈 — **항상 최대 창을 캐시하고 요청분만 잘라 쓴다**.

        `quarters`를 캐시 키에 넣으면 화면이 4/8/20분기를 오갈 때 캐시가 조각나
        히트율이 떨어진다. 시도당 엔트리 1개로 유지한다.
        """
        async def compute() -> list[QuarterValue]:
            stmt, gu = _sido_join(select(fact_orm.year_quarter, func.sum(value_col)), fact_orm)
            rows = (await self._session.execute(
                stmt.where(gu.parent_code == sido_code)
                .group_by(fact_orm.year_quarter)
                .order_by(fact_orm.year_quarter.desc())
                .limit(MAX_QUARTERS)
            )).all()
            return [
                QuarterValue(year_quarter=yq, value=float(total)) for yq, total in reversed(rows)
            ]

        return await self._cached_city((key, sido_code), fact_orm, compute)

    async def find_city_sales_series(self, sido_code: str, quarters: int) -> list[QuarterValue]:
        full = await self._city_series(
            "sales", sido_code, EstimatedSalesOrm, EstimatedSalesOrm.monthly_sales_amount
        )
        return full[-quarters:]

    async def find_city_floating_series(
        self, sido_code: str, quarters: int
    ) -> list[QuarterValue]:
        full = await self._city_series(
            "floating", sido_code, FloatingPopulationOrm,
            FloatingPopulationOrm.total_floating_pop,
        )
        return full[-quarters:]

    async def find_store_health(self, trdar_code: int) -> StoreHealthStat | None:
        latest_quarter = (await self._session.execute(
            select(func.max(StoreOrm.year_quarter)).where(StoreOrm.trdar_code == trdar_code)
        )).scalar()
        if latest_quarter is None:
            return None
        opening, closure = (await self._session.execute(
            select(func.avg(StoreOrm.opening_rate), func.avg(StoreOrm.closure_rate))
            .where(StoreOrm.trdar_code == trdar_code, StoreOrm.year_quarter == latest_quarter)
        )).one()
        return StoreHealthStat(
            year_quarter=latest_quarter,
            opening_rate=float(opening), closure_rate=float(closure),
        )

    async def find_city_store_health(
        self, sido_code: str, year_quarter: int
    ) -> StoreHealthStat | None:
        async def compute() -> StoreHealthStat | None:
            stmt, gu = _sido_join(
                select(func.avg(StoreOrm.opening_rate), func.avg(StoreOrm.closure_rate)),
                StoreOrm,
            )
            opening, closure = (await self._session.execute(
                stmt.where(gu.parent_code == sido_code, StoreOrm.year_quarter == year_quarter)
            )).one()
            if opening is None or closure is None:
                return None
            return StoreHealthStat(
                year_quarter=year_quarter,
                opening_rate=float(opening), closure_rate=float(closure),
            )

        return await self._cached_city(
            ("store_health", sido_code, year_quarter), StoreOrm, compute
        )

    async def find_persistence(
        self, trdar_code: int, sido_code: str | None
    ) -> PersistenceStat | None:
        row = (await self._session.execute(
            select(CommercialChangeOrm.year_quarter, CommercialChangeOrm.operating_months_avg)
            .where(CommercialChangeOrm.trdar_code == trdar_code)
            .order_by(CommercialChangeOrm.year_quarter.desc())
            .limit(1)
        )).first()
        if row is None:
            return None
        year_quarter, operating = row
        region_avg = None
        if sido_code:
            region_avg = (await self._session.execute(
                select(CommercialChangeBenchmarkOrm.operating_months_avg).where(
                    CommercialChangeBenchmarkOrm.region_code == sido_code,
                    CommercialChangeBenchmarkOrm.year_quarter == year_quarter,
                )
            )).scalar()
        return PersistenceStat(
            year_quarter=year_quarter,
            operating_months_avg=float(operating),
            region_operating_months_avg=float(region_avg) if region_avg is not None else None,
        )
