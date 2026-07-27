from __future__ import annotations

from fastapi import Depends

from admin.app.ports.input.dashboard_use_case import DashboardUseCase
from admin.app.use_cases.dashboard_interactor import DashboardInteractor
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.member_directory_port import MemberDirectoryPort
from hub.app.ports.output.recommendation_directory_port import RecommendationDirectoryPort
from hub.app.ports.output.stock_demand_port import StockDemandPort
from hub.dependencies.commercial_data_provider import get_commercial_data_port
from hub.dependencies.member_directory_provider import get_member_directory_port
from hub.dependencies.recommendation_directory_provider import get_recommendation_directory_port
from hub.dependencies.stock_demand_provider import get_stock_demand_port


def get_dashboard_use_case(
    members: MemberDirectoryPort = Depends(get_member_directory_port),
    recommendations: RecommendationDirectoryPort = Depends(get_recommendation_directory_port),
    commercial: CommercialDataPort = Depends(get_commercial_data_port),
    demands: StockDemandPort = Depends(get_stock_demand_port),
) -> DashboardUseCase:
    return DashboardInteractor(
        members=members,
        recommendations=recommendations,
        commercial=commercial,
        demands=demands,
    )
