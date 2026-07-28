from fastapi import APIRouter, Depends, Response

from market.adapter.inbound.api.schemas.area_showcase_schema import (
    AreaShowcaseResponse,
    AreaShowcaseRowSchema,
    DivisionMedianSchema,
)
from market.app.ports.input.area_ranking_use_case import AreaRankingUseCase
from market.dependencies.area_ranking_provider import get_area_ranking_use_case

# `/myself`를 두지 않는다 — market의 자기소개는 cartographer_router가 이미 갖고 있고,
# 이 앱의 조회 슬라이스 라우터는 전부 prefix="/market"이라 또 만들면 라우트가 중복 등록된다.
area_showcase_router = APIRouter(prefix="/market", tags=["market"])


@area_showcase_router.get("/areas/showcase", response_model=AreaShowcaseResponse)
async def get_area_showcase(
    response: Response,
    use_case: AreaRankingUseCase = Depends(get_area_ranking_use_case),
) -> AreaShowcaseResponse:
    """비로그인 첫 화면 쇼케이스 — **이 앱에서 인증 없이 열리는 유일한 조회 경로다.**

    필드를 늘리려면 dto(AreaShowcaseRow)의 제외 사유 주석을 먼저 읽을 것.
    """
    view = await use_case.showcase()
    # 분기 데이터는 분기당 1회만 바뀐다. 앞단 cloudflared가 반복 트래픽을 흡수해
    # 인터랙터 캐시 앞에 한 겹을 더 둔다(rate limit이 붙기 전까지의 방어선).
    response.headers["Cache-Control"] = "public, max-age=3600"
    return AreaShowcaseResponse(
        yearQuarter=view.year_quarter,
        quarterFrom=view.quarter_from,
        areaCount=view.area_count,
        minStoreCount=view.min_store_count,
        rows=[
            AreaShowcaseRowSchema(
                trdarCode=r.trdar_code,
                trdarName=r.trdar_name,
                districtName=r.district_name,
                divisionName=r.division_name,
                salesPerStore=r.sales_per_store,
                storeCount=r.store_count,
            )
            for r in view.rows
        ],
        divisionMedians=[
            DivisionMedianSchema(
                divisionName=d.division_name,
                areaCount=d.area_count,
                medianSalesPerStore=d.median_sales_per_store,
            )
            for d in view.division_medians
        ],
    )
