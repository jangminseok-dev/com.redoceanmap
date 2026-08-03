from fastapi import APIRouter, Depends, HTTPException, Query

from game.adapter.inbound.api.schemas.area_fitness_schema import (
    AreaFitnessResponseSchema,
    DiagnosisSchema,
    FitnessComponentSchema,
)
from game.app.dtos.area_fitness_dto import AreaFitnessQuery
from game.app.exceptions import AreaProfileUnavailable
from game.app.ports.input.area_fitness_use_case import AreaFitnessUseCase
from game.dependencies.area_fitness_provider import get_area_fitness_use_case

area_fitness_router = APIRouter(prefix="/game", tags=["game"])


@area_fitness_router.get("/areas/{trdar_code}/fitness", response_model=AreaFitnessResponseSchema)
async def preview_fitness(
    trdar_code: int,
    service_code: str = Query(description="업종 코드 (예: CS100010)"),
    use_case: AreaFitnessUseCase = Depends(get_area_fitness_use_case),
) -> AreaFitnessResponseSchema:
    try:
        result = await use_case.preview(
            AreaFitnessQuery(trdar_code=trdar_code, service_code=service_code)
        )
    except AreaProfileUnavailable as e:
        raise HTTPException(status_code=404, detail=e.detail) from e

    return AreaFitnessResponseSchema(
        trdarCode=result.trdar_code,
        trdarName=result.trdar_name,
        serviceCode=result.service_code,
        serviceName=result.service_name,
        observedQuarter=result.observed_quarter,
        observedMonthlySalesAmount=result.observed_monthly_sales_amount,
        observedStoreCount=result.observed_store_count,
        observedSimilarStoreCount=result.observed_similar_store_count,
        observedSalesPerStore=result.observed_sales_per_store,
        observedTicketPrice=result.observed_ticket_price,
        observedClosureRate=result.observed_closure_rate,
        observedOperatingMonthsAvg=result.observed_operating_months_avg,
        fitness=result.fitness,
        totalScore=result.total_score,
        components=[
            FitnessComponentSchema(key=c.key, label=c.label, score=c.score, weight=c.weight)
            for c in result.components
        ],
        simulatedMonthlySalesKrw=result.simulated_monthly_sales_krw,
        diagnoses=[DiagnosisSchema(tone=d.tone, message=d.message) for d in result.diagnoses],
        hasSales=result.has_sales,
        hasStore=result.has_store,
        openable=result.openable,
        assumedMinimumCapitalKrw=result.assumed_minimum_capital_krw,
        assumedViableCapitalKrw=result.assumed_viable_capital_krw,
    )
