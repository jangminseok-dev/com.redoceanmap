from fastapi import APIRouter, Depends, HTTPException, Query

from market.adapter.inbound.api.schemas.area_score_schema import (
    AreaScoreResponse,
    AreaScoreSchema,
    ScoreComponentSchema,
    TrendPointSchema,
)
from market.app.dtos.area_score_dto import AreaScoreQuery
from market.domain.services.area_scorer import MAX_QUARTERS
from market.app.ports.input.area_score_use_case import AreaScoreUseCase
from market.dependencies.area_score_provider import get_area_score_use_case

area_score_router = APIRouter(prefix="/market", tags=["market"])


@area_score_router.get("/trdar/{trdar_code}/score", response_model=AreaScoreResponse)
async def get_area_score(
    trdar_code: int,
    quarters: int = Query(default=8, ge=2, le=MAX_QUARTERS),
    use_case: AreaScoreUseCase = Depends(get_area_score_use_case),
) -> AreaScoreResponse:
    view = await use_case.get_score(AreaScoreQuery(trdar_code=trdar_code, quarters=quarters))
    if view is None:
        raise HTTPException(status_code=404, detail=f"상권을 찾지 못했습니다: {trdar_code}")
    return AreaScoreResponse(
        trdarCode=view.trdar_code,
        trdarName=view.trdar_name,
        districtName=view.district_name,
        score=AreaScoreSchema(
            total=view.score.total,
            grade=view.score.grade,
            components=[
                ScoreComponentSchema(
                    key=c.key, name=c.name, score=c.score,
                    value=c.value, benchmark=c.benchmark,
                )
                for c in view.score.components
            ],
        ) if view.score else None,
        trend=[
            TrendPointSchema(
                yearQuarter=p.year_quarter,
                monthlySales=p.monthly_sales,
                salesQoq=p.sales_qoq,
                totalFloatingPop=p.total_floating_pop,
                floatingQoq=p.floating_qoq,
                salesYoy=p.sales_yoy,
                floatingYoy=p.floating_yoy,
            )
            for p in view.trend
        ],
    )
