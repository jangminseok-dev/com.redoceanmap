from fastapi import APIRouter, Depends

from admin.adapter.inbound.api.schemas.dashboard_schema import (
    CategoryCountSchema,
    DashboardResponseSchema,
    MonthCountSchema,
    RecentRecommendationSchema,
    StockDemandSchema,
)
from admin.app.ports.input.dashboard_use_case import DashboardUseCase
from admin.dependencies.dashboard_provider import get_dashboard_use_case
from core.security import require_permission

dashboard_router = APIRouter(prefix="/admin", tags=["admin"])


@dashboard_router.get(
    "/dashboard",
    response_model=DashboardResponseSchema,
    dependencies=[Depends(require_permission("dashboard:read"))],
)
async def dashboard_summary(
    use_case: DashboardUseCase = Depends(get_dashboard_use_case),
) -> DashboardResponseSchema:
    result = await use_case.summary()
    return DashboardResponseSchema(
        member_total=result.member_total,
        member_new_this_month=result.member_new_this_month,
        area_count=result.area_count,
        latest_quarter=result.latest_quarter,
        recommendation_total=result.recommendation_total,
        recommendation_today=result.recommendation_today,
        monthly=[MonthCountSchema(month=m.month, count=m.count) for m in result.monthly],
        top_categories=[
            CategoryCountSchema(category=c.category, count=c.count) for c in result.top_categories
        ],
        recent=[
            RecentRecommendationSchema(
                id=r.id,
                trdar_code=r.trdar_code,
                trdar_name=r.trdar_name,
                district_name=r.district_name,
                category=r.category,
                created_at=r.created_at,
            )
            for r in result.recent
        ],
        stock_demands=[
            StockDemandSchema(
                ticker=d.ticker, ask_count=d.ask_count, last_asked_at=d.last_asked_at
            )
            for d in result.stock_demands
        ],
    )
