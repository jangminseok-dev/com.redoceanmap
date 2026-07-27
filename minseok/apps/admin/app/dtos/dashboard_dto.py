from __future__ import annotations

from dataclasses import dataclass

from hub.app.dtos.recommendation_directory_dto import (
    CategoryCount,
    MonthCount,
    RecommendationInfo,
)
from hub.app.dtos.stock_demand_dto import StockDemandRow


@dataclass(frozen=True)
class DashboardResponse:
    member_total: int
    member_new_this_month: int
    area_count: int
    latest_quarter: str | None  # 예: "20251" — market 데이터 신선도 표시
    recommendation_total: int
    recommendation_today: int
    monthly: list[MonthCount]  # 최근 12개월 추천 추이
    top_categories: list[CategoryCount]
    recent: list[RecommendationInfo]  # 최근 추천 5건
    # 분석 질문 수요 — 워치리스트 편입 스크립트만 보던 지표를 운영자도 본다
    # (어떤 종목을 사람들이 실제로 묻는가 = 수집 대상 선정의 근거)
    stock_demands: list[StockDemandRow]
