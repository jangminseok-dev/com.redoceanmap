from __future__ import annotations

from market.app.dtos.area_stats_dto import (
    AreaStatsQuery,
    AreaStatsView,
    QuarterStat,
)
from market.app.ports.input.area_stats_use_case import AreaStatsUseCase
from market.app.ports.output.area_stats_repository import AreaStatsRepositoryPort


class AreaStatsInteractor(AreaStatsUseCase):
    """상권 통계 대장 — 팩트별 분기 행을 year_quarter 축으로 병합해 시계열을 만든다."""

    def __init__(self, stats: AreaStatsRepositoryPort) -> None:
        self._stats = stats

    async def get_stats(self, query: AreaStatsQuery) -> AreaStatsView | None:
        header = await self._stats.find_header(query.trdar_code)
        if header is None:
            return None

        service = await self._stats.resolve_service(query.trdar_code, query.service_code)
        sales = (
            await self._stats.find_sales(query.trdar_code, service.code, query.quarters)
            if service else []
        )
        stores = (
            await self._stats.find_stores(query.trdar_code, service.code, query.quarters)
            if service else []
        )
        floating = await self._stats.find_floating(query.trdar_code, query.quarters)
        change = await self._stats.find_change(query.trdar_code)

        sales_map = {s.year_quarter: s for s in sales}
        store_map = {s.year_quarter: s for s in stores}
        floating_map = {f.year_quarter: f for f in floating}
        quarters = sorted(set(sales_map) | set(store_map) | set(floating_map))[-query.quarters:]

        series = []
        for yq in quarters:
            s, st, fp = sales_map.get(yq), store_map.get(yq), floating_map.get(yq)
            series.append(QuarterStat(
                year_quarter=yq,
                monthly_sales=s.monthly_sales_amount if s else None,
                weekday_sales=s.weekday_sales_amount if s else None,
                store_count=st.store_count if st else None,
                opening_rate=st.opening_rate if st else None,
                closure_rate=st.closure_rate if st else None,
                franchise_count=st.franchise_store_count if st else None,
                similar_industry_count=st.similar_industry_store_count if st else None,
                opening_count=st.opening_store_count if st else None,
                closure_count=st.closure_store_count if st else None,
                total_floating_pop=fp.total if fp else None,
            ))

        return AreaStatsView(
            trdar_code=header.trdar_code,
            trdar_name=header.trdar_name,
            district_name=header.district_name,
            service_code=service.code if service else None,
            service_name=service.name if service else None,
            series=series,
            latest_floating=floating[-1] if floating else None,
            change=change,
        )
