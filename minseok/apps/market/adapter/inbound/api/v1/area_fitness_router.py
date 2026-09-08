from fastapi import APIRouter, Depends, HTTPException, Query

from market.adapter.inbound.api.schemas.area_fitness_schema import (
    AreaFitnessResponse,
    DiagnosisSchema,
    FitnessComponentSchema,
)
from market.app.dtos.area_fitness_dto import AreaFitnessQuery
from market.app.ports.input.area_fitness_use_case import AreaFitnessUseCase
from market.dependencies.area_fitness_provider import get_area_fitness_use_case

area_fitness_router = APIRouter(prefix="/market", tags=["market"])


@area_fitness_router.get("/trdar/{trdar_code}/fitness", response_model=AreaFitnessResponse)
async def get_area_fitness(
    trdar_code: int,
    service_code: str = Query(description="업종 코드 (예: CS100010)"),
    use_case: AreaFitnessUseCase = Depends(get_area_fitness_use_case),
) -> AreaFitnessResponse:
    view = await use_case.evaluate(AreaFitnessQuery(trdar_code=trdar_code, service_code=service_code))
    if view is None:
        raise HTTPException(
            status_code=404, detail=f"상권 {trdar_code} · 업종 {service_code}의 자료가 없습니다"
        )
    return AreaFitnessResponse(
        trdarCode=view.trdar_code,
        trdarName=view.trdar_name,
        serviceCode=view.service_code,
        serviceName=view.service_name,
        yearQuarter=view.year_quarter,
        observedMonthlySalesAmount=view.observed_monthly_sales_amount,
        observedStoreCount=view.observed_store_count,
        observedSimilarStoreCount=view.observed_similar_store_count,
        observedSalesPerStore=view.observed_sales_per_store,
        observedTicketPrice=view.observed_ticket_price,
        observedClosureRate=view.observed_closure_rate,
        observedOperatingMonthsAvg=view.observed_operating_months_avg,
        totalScore=view.total_score,
        components=[
            FitnessComponentSchema(key=c.key, label=c.label, score=c.score, weight=c.weight)
            for c in view.components
        ],
        diagnoses=[DiagnosisSchema(tone=d.tone, message=d.message) for d in view.diagnoses],
        hasSales=view.has_sales,
        hasStore=view.has_store,
    )
