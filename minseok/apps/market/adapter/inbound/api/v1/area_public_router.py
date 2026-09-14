from fastapi import APIRouter, Depends, HTTPException, Response

from core.rate_limit import rate_limit
from market.adapter.inbound.api.schemas.area_public_schema import (
    AreaIndexResponse,
    AreaIndexRowSchema,
    AreaPublicResponse,
    PublicInsightSchema,
    PublicScoreComponentSchema,
    PublicScoreSchema,
)
from market.app.ports.input.area_public_use_case import AreaPublicUseCase
from market.dependencies.area_public_provider import get_area_public_use_case

# `/myself`를 두지 않는다 — showcase와 같은 이유(조회 슬라이스 라우터가 전부 prefix="/market").
area_public_router = APIRouter(prefix="/market", tags=["market"])

# 인증이 없는 대신 IP 빈도 제한이 방어선이다(cloudflared가 CF-Connecting-IP를 덮어써 위조 불가).
# 분기 데이터라 하루 캐시 — 앞단 cloudflared·Next ISR이 반복 트래픽을 흡수한다.
_CACHE = "public, max-age=86400"


@area_public_router.get(
    "/areas/public-index",
    response_model=AreaIndexResponse,
    dependencies=[rate_limit("public_area_index", limit=10, window_seconds=60)],
)
async def get_area_public_index(
    response: Response,
    use_case: AreaPublicUseCase = Depends(get_area_public_use_case),
) -> AreaIndexResponse:
    """sitemap용 전 상권 목록 — 코드·이름·자치구·유형뿐(서울시 공개 차원 데이터)."""
    rows = await use_case.list_index()
    response.headers["Cache-Control"] = _CACHE
    return AreaIndexResponse(rows=[
        AreaIndexRowSchema(trdarCode=r.trdar_code, trdarName=r.trdar_name,
                           districtName=r.district_name, divisionName=r.division_name)
        for r in rows
    ])


@area_public_router.get(
    "/areas/{trdar_code}/public",
    response_model=AreaPublicResponse,
    dependencies=[rate_limit("public_area", limit=60, window_seconds=60)],
)
async def get_area_public(
    trdar_code: int,
    response: Response,
    use_case: AreaPublicUseCase = Depends(get_area_public_use_case),
) -> AreaPublicResponse:
    """비로그인 공개 상권 페이지(A-4) — 핵심 요약 + 해석 문장. 필드 절제는 AreaPublicView가 정본."""
    view = await use_case.get_public(trdar_code)
    if view is None:
        raise HTTPException(status_code=404, detail=f"상권을 찾지 못했습니다: {trdar_code}")
    response.headers["Cache-Control"] = _CACHE
    return AreaPublicResponse(
        trdarCode=view.trdar_code,
        trdarName=view.trdar_name,
        districtName=view.district_name,
        divisionName=view.division_name,
        yearQuarter=view.year_quarter,
        score=PublicScoreSchema(
            total=view.score.total,
            grade=view.score.grade,
            components=[
                PublicScoreComponentSchema(key=c.key, name=c.name, score=c.score,
                                           value=c.value, benchmark=c.benchmark)
                for c in view.score.components
            ],
        ) if view.score else None,
        serviceCode=view.service_code,
        serviceName=view.service_name,
        storeCount=view.store_count,
        salesPerStore=view.sales_per_store,
        salesQoq=view.sales_qoq,
        closureRate=view.closure_rate,
        floatingPop=view.floating_pop,
        insights=[PublicInsightSchema(key=i.key, tone=i.tone, text=i.text) for i in view.insights],
    )
