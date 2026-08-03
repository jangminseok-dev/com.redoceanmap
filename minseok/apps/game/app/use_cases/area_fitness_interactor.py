from __future__ import annotations

from game.app.dtos.area_fitness_dto import (
    AreaFitnessQuery,
    AreaFitnessView,
    DiagnosisView,
    FitnessComponentView,
)
from game.app.exceptions import AreaProfileUnavailable
from game.app.ports.input.area_fitness_use_case import AreaFitnessUseCase
from game.domain.clock.game_epoch import DATA_QUARTER
from game.domain.commerce import diagnosis as diagnosis_rules
from game.domain.commerce import fitness as fitness_rules
from game.domain.commerce import store_simulation as sim
from hub.app.ports.output.area_demand_profile_port import AreaDemandProfilePort


class AreaFitnessInteractor(AreaFitnessUseCase):
    """입지 적합도 대장.

    실데이터 분기는 **에포크에 박힌 값**을 쓴다(game-harness §1-5). market이 새 분기를
    적재해도 진행 중인 시즌의 기준선은 바뀌지 않는다 — 어느 날 갑자기 모든 유저의 가게
    매출이 달라지면 안 된다.
    """

    def __init__(self, profiles: AreaDemandProfilePort) -> None:
        self._profiles = profiles

    async def preview(self, query: AreaFitnessQuery) -> AreaFitnessView:
        profile = await self._profiles.get_demand_profile(
            trdar_code=query.trdar_code,
            service_code=query.service_code,
            year_quarter=DATA_QUARTER,
        )
        if profile is None:
            raise AreaProfileUnavailable(
                f"상권 {query.trdar_code} · 업종 {query.service_code}의 자료가 없습니다"
            )

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

        # 점포당 기대매출 — (분기, 상권, 업종) 축이 일치해야 한다.
        # ⚠️ similar_industry_store_count와 섞지 않는다(game-strategy §4-1 집계 축 함정).
        sales_per_store = (
            profile.observed_monthly_sales_amount // max(profile.observed_store_count, 1)
        )
        ticket_price = (
            profile.observed_monthly_sales_amount // max(profile.observed_monthly_sales_count, 1)
        )

        # 창업이 성립하는가 — store_open_interactor의 거절 조건과 **같은 판정**이다.
        # 화면이 "열 수 없는 자리"를 열 수 있는 것처럼 보여주지 않게 여기서 미리 답한다.
        openable = sales_per_store > 0
        rent_location = sim.rent_location(profile.saturation_percentile)
        capital_args = dict(
            observed_sales_per_store=sales_per_store,
            observed_ticket_price=ticket_price,
            fitness=result.fitness,
            rent_location_factor=rent_location,
            service_code=profile.service_code,
        )
        # 두 경계를 함께 준다 — 창업이 되는 금액과, 손님이 오기 시작하는 금액은 다르다.
        minimum_capital = sim.minimum_capital(**capital_args) if openable else 0
        viable_capital = sim.viable_capital(**capital_args) if openable else 0

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
            observed_quarter=profile.year_quarter,
            observed_monthly_sales_amount=profile.observed_monthly_sales_amount,
            observed_store_count=profile.observed_store_count,
            observed_similar_store_count=profile.observed_similar_store_count,
            observed_sales_per_store=sales_per_store,
            observed_ticket_price=ticket_price,
            observed_closure_rate=profile.observed_closure_rate,
            observed_operating_months_avg=profile.observed_operating_months_avg,
            fitness=result.fitness,
            total_score=result.total_score,
            components=tuple(
                FitnessComponentView(key=c.key, label=c.label, score=c.score, weight=c.weight)
                for c in result.components
            ),
            simulated_monthly_sales_krw=round(sales_per_store * result.fitness),
            diagnoses=tuple(
                DiagnosisView(tone=d.tone, message=d.message) for d in diagnoses
            ),
            has_sales=profile.has_sales,
            has_store=profile.has_store,
            openable=openable,
            assumed_minimum_capital_krw=minimum_capital,
            assumed_viable_capital_krw=viable_capital,
        )
