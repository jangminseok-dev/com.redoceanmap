from __future__ import annotations

from admin.app.dtos.dashboard_dto import DashboardResponse
from admin.app.ports.input.dashboard_use_case import DashboardUseCase
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.member_directory_port import MemberDirectoryPort
from hub.app.ports.output.recommendation_directory_port import RecommendationDirectoryPort
from hub.app.ports.output.stock_demand_port import StockDemandPort

RECENT_LIMIT = 5
DEMAND_DAYS = 30   # 워치리스트 편입 스크립트와 같은 창
DEMAND_LIMIT = 10


class DashboardInteractor(DashboardUseCase):
    """어드민 대시보드 대장 — 허브 포트 4개를 합성해 KPI를 만든다."""

    def __init__(
        self,
        members: MemberDirectoryPort,
        recommendations: RecommendationDirectoryPort,
        commercial: CommercialDataPort,
        demands: StockDemandPort,
    ) -> None:
        self._members = members
        self._recommendations = recommendations
        self._commercial = commercial
        self._demands = demands

    async def summary(self) -> DashboardResponse:
        member_stats = await self._members.member_stats()
        rec_stats = await self._recommendations.stats()
        recent = await self._recommendations.list_recent(RECENT_LIMIT)
        dataset_stats = await self._commercial.get_dataset_stats()
        demands = await self._demands.top_demands(DEMAND_DAYS, DEMAND_LIMIT)

        by_key = {s.key: s for s in dataset_stats}
        area_count = by_key["trade_area"].row_count if "trade_area" in by_key else 0
        latest_quarter = by_key["estimated_sales"].latest_label if "estimated_sales" in by_key else None

        return DashboardResponse(
            member_total=member_stats.total,
            member_new_this_month=member_stats.new_this_month,
            area_count=area_count,
            latest_quarter=latest_quarter,
            recommendation_total=rec_stats.total,
            recommendation_today=rec_stats.today,
            monthly=rec_stats.monthly,
            top_categories=rec_stats.top_categories,
            recent=recent,
            stock_demands=demands,
        )
