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

        # 추이(QoQ·YoY)는 화면 표시용 — 점수 v2는 추이가 아니라 생존 축을 쓴다(area_scorer 모듈 주석)
        sales_series = await self._repo.find_sales_series(query.trdar_code, query.quarters)
        floating_series = await self._repo.find_floating_series(query.trdar_code, query.quarters)

        score = None
        inputs = await self._repo.find_score_inputs(query.trdar_code)
        medians = await self._repo.find_city_score_medians(header.sido_code) if inputs and header.sido_code else None
        if inputs is not None and medians is not None:
            score = self._scorer.score(
                closure_stability=self._pair(inputs.closure_rate_4q, medians.closure_rate_4q),
                persistence=self._pair(inputs.operating_months, medians.operating_months),
                sales_level=self._pair(inputs.sales_per_store_wan, medians.sales_per_store_wan),
            )

        return AreaScoreView(
            trdar_code=header.trdar_code,
            trdar_name=header.trdar_name,
            district_name=header.district_name,
            score=score,
            trend=self._merge_trend(
                self._scorer.qoq_series(sales_series), self._scorer.qoq_series(floating_series),
                self._scorer.yoy_series(sales_series), self._scorer.yoy_series(floating_series),
            ),
        )

    @staticmethod
    def _pair(value: float | None, benchmark: float | None) -> MetricComparison | None:
        if value is None or benchmark is None:
            return None
        return MetricComparison(value=round(value, 2), benchmark=round(benchmark, 2))

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
