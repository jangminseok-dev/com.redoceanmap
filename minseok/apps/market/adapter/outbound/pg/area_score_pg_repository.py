from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from market.adapter.outbound.orm.estimated_sales_orm import EstimatedSalesOrm
from market.adapter.outbound.orm.floating_population_orm import FloatingPopulationOrm
from market.adapter.outbound.orm.region_orm import RegionOrm
from market.adapter.outbound.orm.store_orm import StoreOrm
from market.adapter.outbound.orm.trade_area_orm import TradeAreaOrm
from market.app.dtos.area_score_dto import AreaScoreHeader
from market.app.ports.output.area_score_repository import AreaScoreRepositoryPort
from market.domain.services.area_scorer import (
    inputs_from_aggregates,
    median_inputs,
    prev_quarter,
)
from market.domain.value_objects.area_score_vo import AreaScoreInputs, QuarterValue
from market.domain.value_objects.sales_unit import monthly_from_quarter

# 점수 v2 입력 — 최신 점포 분기 q0 기준. 폐업률은 q0~q3 점포 가중,
# 점포당 매출은 q0에서 매출·점포가 같은 업종으로 짝지어진 것만(업종 축 불일치 방지). scope는 상권 1곳 또는 시도 전체.
_SCORE_INPUTS_SQL = """
WITH st AS (
    SELECT s.trdar_code, s.year_quarter, SUM(s.store_count) AS sc, SUM(s.closure_store_count) AS cc
    FROM store s
    WHERE s.year_quarter IN (:q0, :q1, :q2, :q3) {scope}
    GROUP BY s.trdar_code, s.year_quarter
), agg AS (
    SELECT trdar_code,
           SUM(cc) * 100.0 / NULLIF(SUM(sc), 0) AS closure4,
           COUNT(*) AS n4,
           MAX(sc) FILTER (WHERE year_quarter = :q0) AS sc0
    FROM st GROUP BY trdar_code
), sal AS (
    SELECT es.trdar_code, SUM(es.monthly_sales_amount) AS amt, SUM(s.store_count) AS sal_sc
    FROM estimated_sales es
    JOIN store s ON s.trdar_code = es.trdar_code AND s.year_quarter = es.year_quarter
                AND s.service_code = es.service_code
    WHERE es.year_quarter = :q0 AND s.store_count > 0 {scope}
    GROUP BY es.trdar_code
), om AS (
    SELECT DISTINCT ON (trdar_code) trdar_code, operating_months_avg AS om
    FROM commercial_change {om_where}
    ORDER BY trdar_code, year_quarter DESC
)
SELECT agg.trdar_code, agg.closure4, agg.n4, agg.sc0, sal.amt, sal.sal_sc, om.om
FROM agg LEFT JOIN sal USING (trdar_code) LEFT JOIN om USING (trdar_code)
WHERE agg.sc0 IS NOT NULL
"""


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

    async def _score_input_rows(self, *, trdar_code: int | None, sido_code: str | None) -> tuple[int, list]:
        """점수 v2 입력의 상권별 원행 — trdar_code를 주면 그 상권만, sido_code를 주면 시도 안 전체."""
        q0 = await self._latest_quarter(StoreOrm)
        if q0 is None:
            return 0, []
        q1 = prev_quarter(q0)
        q2 = prev_quarter(q1)
        q3 = prev_quarter(q2)
        if trdar_code is not None:
            scope = "AND s.trdar_code = :code"
            om_where = "WHERE trdar_code = :code"
        else:
            scope = ("AND s.trdar_code IN (SELECT ta.code FROM trade_area ta JOIN region dong ON ta.region_code = dong.code"
                     " JOIN region gu ON dong.parent_code = gu.code WHERE gu.parent_code = :sido)")
            om_where = ""
        rows = (await self._session.execute(text(_SCORE_INPUTS_SQL.format(scope=scope, om_where=om_where)), {
            "q0": q0, "q1": q1, "q2": q2, "q3": q3, "code": trdar_code, "sido": sido_code,
        })).all()
        return q0, rows

    @staticmethod
    def _to_inputs(q0: int, row) -> AreaScoreInputs:
        return inputs_from_aggregates(
            year_quarter=q0, closure_rate_4q=row.closure4, quarters_with_stores=row.n4,
            store_count=row.sc0,
            quarterly_sales=row.amt, sales_store_count=row.sal_sc, operating_months=row.om,
        )

    async def find_score_inputs(self, trdar_code: int) -> AreaScoreInputs | None:
        q0, rows = await self._score_input_rows(trdar_code=trdar_code, sido_code=None)
        return self._to_inputs(q0, rows[0]) if rows else None

    async def find_city_score_medians(self, sido_code: str) -> AreaScoreInputs | None:
        async def compute() -> AreaScoreInputs | None:
            q0, rows = await self._score_input_rows(trdar_code=None, sido_code=sido_code)
            return median_inputs(q0, [self._to_inputs(q0, r) for r in rows])

        return await self._cached_city(("score_medians", sido_code), StoreOrm, compute)
