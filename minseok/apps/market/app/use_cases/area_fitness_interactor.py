from __future__ import annotations

from market.app.dtos.area_fitness_dto import (
    AreaFitnessQuery,
    AreaFitnessView,
    DiagnosisView,
    FitnessComponentView,
)
from market.app.ports.input.area_fitness_use_case import AreaFitnessUseCase
from market.app.ports.output.area_demand_profile_port import AreaDemandProfilePort
from market.domain.services import area_fitness as fitness_rules
from market.domain.services import area_fitness_narrator as diagnosis_rules


class AreaFitnessInteractor(AreaFitnessUseCase):
    """입지 적합도 대장. 분기는 **최신 적재 분기**를 쓴다(area_stats·area_ranking과 같은 규칙)."""

    def __init__(self, profiles: AreaDemandProfilePort) -> None:
        self._profiles = profiles

    async def evaluate(self, query: AreaFitnessQuery) -> AreaFitnessView | None:
        year_quarter = await self._profiles.latest_quarter()
        if year_quarter is None:
            return None
        profile = await self._profiles.get_demand_profile(
            trdar_code=query.trdar_code,
            service_code=query.service_code,
            year_quarter=year_quarter,
        )
        if profile is None:
            return None

        result = fitness_rules.evaluate(
            industry_age_share=profile.industry_age_share,
            industry_gender_share=profile.industry_gender_share,
            industry_hour_share=profile.industry_hour_share,
            floating_age_share=profile.floating_age_share,
            floating_gender_share=profile.floating_gender_share,
            floating_hour_share=profile.floating_hour_share,
            saturation_percentile=profile.saturation_percentile,
            closure_rate_percentile=profile.closure_rate_percentile,
            operating_months_percentile=profile.operating_months_percentile,
            has_store=profile.has_store,
        )

        # 점포당 매출·객단가 — (분기, 상권, 업종) 축이 일치해야 한다.
        # ⚠️ similar_industry_store_count와 섞지 않는다(집계 축이 다르다).
        sales_per_store = (
            profile.observed_monthly_sales_amount // max(profile.observed_store_count, 1)
        )
        ticket_price = (
            profile.observed_monthly_sales_amount // max(profile.observed_monthly_sales_count, 1)
        )

        diagnoses = diagnosis_rules.diagnose(
            service_name=profile.service_name,
            industry_age_share=profile.industry_age_share,
            floating_age_share=profile.floating_age_share,
            industry_hour_share=profile.industry_hour_share,
            floating_hour_share=profile.floating_hour_share,
            saturation_percentile=profile.saturation_percentile,
            closure_rate_percentile=profile.closure_rate_percentile,
            similar_store_count=profile.observed_similar_store_count,
            operating_months_avg=profile.observed_operating_months_avg,
            has_sales=profile.has_sales,
            has_store=profile.has_store,
        )

        return AreaFitnessView(
            trdar_code=profile.trdar_code,
            trdar_name=profile.trdar_name,
            service_code=profile.service_code,
            service_name=profile.service_name,
            year_quarter=profile.year_quarter,
            observed_monthly_sales_amount=profile.observed_monthly_sales_amount,
            observed_store_count=profile.observed_store_count,
            observed_similar_store_count=profile.observed_similar_store_count,
            observed_sales_per_store=sales_per_store,
            observed_ticket_price=ticket_price,
            observed_closure_rate=profile.observed_closure_rate,
            observed_operating_months_avg=profile.observed_operating_months_avg,
            total_score=result.total_score,
            components=tuple(
                FitnessComponentView(key=c.key, label=c.label, score=c.score, weight=c.weight)
                for c in result.components
            ),
            diagnoses=tuple(DiagnosisView(tone=d.tone, message=d.message) for d in diagnoses),
            has_sales=profile.has_sales,
            has_store=profile.has_store,
        )
