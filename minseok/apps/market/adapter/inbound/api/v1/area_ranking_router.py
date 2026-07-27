from fastapi import APIRouter, Depends, Query

from market.adapter.inbound.api.schemas.area_ranking_schema import (
    AreaRankingResponse,
    AreaRankingRowSchema,
    ServiceOptionSchema,
)
from market.app.dtos.area_ranking_dto import AreaRankingQuery
from market.app.ports.input.area_ranking_use_case import AreaRankingUseCase
from market.dependencies.area_ranking_provider import get_area_ranking_use_case

area_ranking_router = APIRouter(prefix="/market", tags=["market"])


@area_ranking_router.get("/areas/ranking", response_model=AreaRankingResponse)
async def list_area_ranking(
    gu: str | None = Query(default=None, description="자치구명 (예: 성동구)"),
    division: str | None = Query(default=None, description="상권 구분 코드"),
    service_code: str | None = Query(default=None, description="업종 코드 — 지정 시 해당 업종만 집계"),
    use_case: AreaRankingUseCase = Depends(get_area_ranking_use_case),
) -> AreaRankingResponse:
    # 조건에 맞는 상권이 없어도 404가 아니다 — 목록 화면은 빈 상태로라도 떠야 한다.
    view = await use_case.list_ranking(AreaRankingQuery(
        district_name=gu, division_code=division, service_code=service_code,
    ))
    return AreaRankingResponse(
        yearQuarter=view.year_quarter,
        rows=[
            AreaRankingRowSchema(
                trdarCode=r.trdar_code,
                trdarName=r.trdar_name,
                districtName=r.district_name,
                dongName=r.dong_name,
                divisionCode=r.division_code,
                divisionName=r.division_name,
                lat=r.lat,
                lng=r.lng,
                monthlySales=r.monthly_sales,
                storeCount=r.store_count,
                salesPerStore=r.sales_per_store,
                salesQoq=r.sales_qoq,
                closureRate=r.closure_rate,
            )
            for r in view.rows
        ],
        services=[ServiceOptionSchema(code=s.code, name=s.name) for s in view.services],
    )
