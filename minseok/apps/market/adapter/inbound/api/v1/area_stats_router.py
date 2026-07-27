from fastapi import APIRouter, Depends, HTTPException, Query

from market.adapter.inbound.api.schemas.area_stats_schema import (
    AreaStatsLatestSchema,
    AreaStatsResponse,
    FloatingByAgeSchema,
    FloatingByTimeSchema,
    QuarterStatSchema,
)
from market.app.dtos.area_stats_dto import AreaStatsQuery
from market.app.ports.input.area_stats_use_case import AreaStatsUseCase
from market.dependencies.area_stats_provider import get_area_stats_use_case

area_stats_router = APIRouter(prefix="/market", tags=["market"])


@area_stats_router.get("/trdar/{trdar_code}/stats", response_model=AreaStatsResponse)
async def get_area_stats(
    trdar_code: int,
    service_code: str | None = None,
    quarters: int = Query(default=4, ge=1, le=12),
    use_case: AreaStatsUseCase = Depends(get_area_stats_use_case),
) -> AreaStatsResponse:
    view = await use_case.get_stats(
        AreaStatsQuery(trdar_code=trdar_code, service_code=service_code, quarters=quarters)
    )
    if view is None:
        raise HTTPException(status_code=404, detail=f"상권을 찾지 못했습니다: {trdar_code}")
    fp = view.latest_floating
    return AreaStatsResponse(
        trdarCode=view.trdar_code,
        trdarName=view.trdar_name,
        districtName=view.district_name,
        serviceCode=view.service_code,
        serviceName=view.service_name,
        series=[
            QuarterStatSchema(
                yearQuarter=q.year_quarter,
                monthlySales=q.monthly_sales,
                weekdaySales=q.weekday_sales,
                storeCount=q.store_count,
                openingRate=q.opening_rate,
                closureRate=q.closure_rate,
                franchiseCount=q.franchise_count,
                similarIndustryCount=q.similar_industry_count,
                openingCount=q.opening_count,
                closureCount=q.closure_count,
                totalFloatingPop=q.total_floating_pop,
            )
            for q in view.series
        ],
        latest=AreaStatsLatestSchema(
            floatingByAge=FloatingByAgeSchema(
                age10=fp.age_10, age20=fp.age_20, age30=fp.age_30,
                age40=fp.age_40, age50=fp.age_50, age60Plus=fp.age_60_plus,
            ) if fp else None,
            floatingByTime=FloatingByTimeSchema(
                t00_06=fp.time_00_06, t06_11=fp.time_06_11, t11_14=fp.time_11_14,
                t14_17=fp.time_14_17, t17_21=fp.time_17_21, t21_24=fp.time_21_24,
            ) if fp else None,
            changeIndicator=view.change.change_indicator_name if view.change else None,
            operatingMonthsAvg=view.change.operating_months_avg if view.change else None,
            regionOperatingMonthsAvg=(
                view.change.region_operating_months_avg if view.change else None
            ),
            closureMonthsAvg=view.change.closure_months_avg if view.change else None,
            regionClosureMonthsAvg=(
                view.change.region_closure_months_avg if view.change else None
            ),
        ),
    )
