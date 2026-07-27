from fastapi import APIRouter, Depends, HTTPException

from market.adapter.inbound.api.schemas.area_detail_schema import (
    FacilitySchema,
    FloatingRhythmSchema,
    AgeBandSchema,
    ApartmentSchema,
    AreaDetailResponse,
    DemandSchema,
    HouseholdsSchema,
    InsightSchema,
    PopulationSchema,
    SalesMixSchema,
    SpendingCategorySchema,
    SpendingSchema,
)
from market.app.dtos.area_detail_dto import AreaDetailQuery, AreaDetailView
from market.app.ports.input.area_detail_use_case import AreaDetailUseCase
from market.dependencies.area_detail_provider import get_area_detail_use_case

area_detail_router = APIRouter(prefix="/market", tags=["market"])


@area_detail_router.get("/trdar/{trdar_code}/detail", response_model=AreaDetailResponse)
async def get_area_detail(
    trdar_code: int,
    service_code: str | None = None,
    use_case: AreaDetailUseCase = Depends(get_area_detail_use_case),
) -> AreaDetailResponse:
    view = await use_case.get_detail(
        AreaDetailQuery(trdar_code=trdar_code, service_code=service_code)
    )
    if view is None:
        raise HTTPException(status_code=404, detail=f"상권을 찾지 못했습니다: {trdar_code}")
    return AreaDetailResponse(
        trdarCode=view.trdar_code,
        trdarName=view.trdar_name,
        districtName=view.district_name,
        serviceCode=view.service_code,
        serviceName=view.service_name,
        salesMix=SalesMixSchema(
            yearQuarter=view.sales_mix.year_quarter,
            weekdayAmount=view.sales_mix.weekday_amount,
            weekendAmount=view.sales_mix.weekend_amount,
            byDay=view.sales_mix.by_day,
            byTime=view.sales_mix.by_time,
            byGender=view.sales_mix.by_gender,
            byAge=view.sales_mix.by_age,
            monthlyCount=view.sales_mix.monthly_count,
            monthlyAmount=view.sales_mix.monthly_amount,
            weekdayCount=view.sales_mix.weekday_count,
            weekendCount=view.sales_mix.weekend_count,
            countByAge=view.sales_mix.count_by_age,
        ) if view.sales_mix else None,
        demand=_demand_schema(view),
        spending=SpendingSchema(
            yearQuarter=view.spending.year_quarter,
            monthlyAvgIncome=view.spending.monthly_avg_income,
            totalExpenditure=view.spending.total_expenditure,
            byCategory=[
                SpendingCategorySchema(key=c.key, label=c.label, amount=c.amount)
                for c in view.spending.by_category
            ],
        ) if view.spending else None,
        floating=FloatingRhythmSchema(
            yearQuarter=view.floating.year_quarter,
            weekdayPop=view.floating.weekday_pop,
            weekendPop=view.floating.weekend_pop,
        ) if view.floating else None,
        facility=FacilitySchema(
            yearQuarter=view.facility.year_quarter,
            total=view.facility.total,
            subwayStations=view.facility.subway_stations,
            busStops=view.facility.bus_stops,
            universities=view.facility.universities,
            departmentStores=view.facility.department_stores,
            hospitals=view.facility.hospitals,
        ) if view.facility else None,
        insights=[
            InsightSchema(key=i.key, tone=i.tone, text=i.text) for i in view.insights
        ],
    )


def _demand_schema(view: AreaDetailView) -> DemandSchema | None:
    if view.resident is None and view.working is None and view.apartment is None:
        return None
    return DemandSchema(
        resident=PopulationSchema(
            yearQuarter=view.resident.year_quarter,
            total=view.resident.total,
            byAge=[
                AgeBandSchema(band=b.band, male=b.male, female=b.female)
                for b in view.resident.by_age
            ],
        ) if view.resident else None,
        working=PopulationSchema(
            yearQuarter=view.working.year_quarter,
            total=view.working.total,
            byAge=[
                AgeBandSchema(band=b.band, male=b.male, female=b.female)
                for b in view.working.by_age
            ],
        ) if view.working else None,
        households=HouseholdsSchema(
            total=view.resident.total_households,
            apartment=view.resident.apartment_households,
        ) if view.resident else None,
        apartment=ApartmentSchema(
            yearQuarter=view.apartment.year_quarter,
            complexCount=view.apartment.complex_count,
            avgPrice=view.apartment.avg_price,
            avgArea=view.apartment.avg_area,
        ) if view.apartment else None,
    )
