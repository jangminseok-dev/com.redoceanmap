from __future__ import annotations

from market.app.dtos.area_score_dto import (
    AreaScoreQuery,
    AreaScoreView,
    TrendPoint,
)
from market.app.ports.input.area_score_use_case import AreaScoreUseCase
from market.app.ports.output.area_score_repository import AreaScoreRepositoryPort
from market.domain.services.area_scorer import AreaScorer
from market.domain.value_objects.area_score_vo import MetricComparison, QoqPoint


class AreaScoreInteractor(AreaScoreUseCase):
    """상권 종합점수 대장 — 팩트 조회를 모아 도메인 스코어러에 계산을 맡긴다."""

    def __init__(self, repo: AreaScoreRepositoryPort, scorer: AreaScorer | None = None) -> None:
        self._repo = repo
        self._scorer = scorer or AreaScorer()

    async def get_score(self, query: AreaScoreQuery) -> AreaScoreView | None:
        header = await self._repo.find_header(query.trdar_code)
        if header is None:
            return None

        # 원시 시리즈를 잡아둔다 — QoQ와 YoY 두 축을 같은 원본에서 낸다(재조회 없음)
        sales_series = await self._repo.find_sales_series(query.trdar_code, query.quarters)
        floating_series = await self._repo.find_floating_series(query.trdar_code, query.quarters)
        sales_trend = self._scorer.qoq_series(sales_series)
        floating_trend = self._scorer.qoq_series(floating_series)

        sales_growth = floating_growth = None
        if header.sido_code:
            city_sales_trend = self._scorer.qoq_series(
                await self._repo.find_city_sales_series(header.sido_code, query.quarters)
            )
            city_floating_trend = self._scorer.qoq_series(
                await self._repo.find_city_floating_series(header.sido_code, query.quarters)
            )
            sales_growth = self._scorer.growth_comparison(sales_trend, city_sales_trend)
            floating_growth = self._scorer.growth_comparison(floating_trend, city_floating_trend)

        store_health = None
        store = await self._repo.find_store_health(query.trdar_code)
        if store and header.sido_code:
            city_store = await self._repo.find_city_store_health(
                header.sido_code, store.year_quarter
            )
            if city_store:
                store_health = MetricComparison(
                    value=store.opening_rate - store.closure_rate,
                    benchmark=city_store.opening_rate - city_store.closure_rate,
                )

        persistence = None
        persistence_stat = await self._repo.find_persistence(query.trdar_code, header.sido_code)
        if persistence_stat and persistence_stat.region_operating_months_avg is not None:
            persistence = MetricComparison(
                value=persistence_stat.operating_months_avg,
                benchmark=persistence_stat.region_operating_months_avg,
            )

        return AreaScoreView(
            trdar_code=header.trdar_code,
            trdar_name=header.trdar_name,
            district_name=header.district_name,
            score=self._scorer.score(
                sales_growth=sales_growth,
                floating_growth=floating_growth,
                store_health=store_health,
                persistence=persistence,
            ),
            trend=self._merge_trend(
                sales_trend, floating_trend,
                self._scorer.yoy_series(sales_series), self._scorer.yoy_series(floating_series),
            ),
        )

    @staticmethod
    def _merge_trend(
        sales_trend: list[QoqPoint],
        floating_trend: list[QoqPoint],
        sales_yoy: list[QoqPoint],
        floating_yoy: list[QoqPoint],
    ) -> list[TrendPoint]:
        sales_map = {p.year_quarter: p for p in sales_trend}
        floating_map = {p.year_quarter: p for p in floating_trend}
        sales_yoy_map = {p.year_quarter: p.qoq_rate for p in sales_yoy}
        floating_yoy_map = {p.year_quarter: p.qoq_rate for p in floating_yoy}
        trend = []
        for yq in sorted(set(sales_map) | set(floating_map)):
            s, fp = sales_map.get(yq), floating_map.get(yq)
            trend.append(TrendPoint(
                year_quarter=yq,
                monthly_sales=int(s.value) if s else None,
                sales_qoq=s.qoq_rate if s else None,
                total_floating_pop=int(fp.value) if fp else None,
                floating_qoq=fp.qoq_rate if fp else None,
                sales_yoy=sales_yoy_map.get(yq),
                floating_yoy=floating_yoy_map.get(yq),
            ))
        return trend
