from admin.app.use_cases.dashboard_interactor import DashboardInteractor
from hub.app.dtos.dataset_stat_dto import DatasetStat
from hub.app.dtos.member_directory_dto import MemberStats
from datetime import datetime

from hub.app.dtos.recommendation_directory_dto import (
    CategoryCount,
    MonthCount,
    RecommendationStats,
)
from hub.app.dtos.stock_demand_dto import StockDemandRow


class _StubMembers:
    async def member_stats(self):
        return MemberStats(total=42, new_this_month=3)


class _StubRecommendations:
    async def stats(self):
        return RecommendationStats(
            total=100,
            today=5,
            monthly=[MonthCount(month="2026-07", count=5)],
            top_categories=[CategoryCount(category="카페", count=30)],
        )

    async def list_recent(self, limit):
        assert limit == 5
        return []


class _StubDemands:
    async def top_demands(self, days, limit):
        assert (days, limit) == (30, 10)  # 워치리스트 편입 스크립트와 같은 창
        return [StockDemandRow(ticker="NVDA", ask_count=7,
                               last_asked_at=datetime(2026, 7, 27, 9, 0))]


class _StubCommercial:
    async def get_dataset_stats(self):
        return [
            DatasetStat(key="trade_area", name="상권", row_count=1742, latest_label=None),
            DatasetStat(key="estimated_sales", name="추정 매출", row_count=9000, latest_label="20251"),
        ]


async def test_대시보드는_허브_포트_4개를_합성한다():
    interactor = DashboardInteractor(
        members=_StubMembers(),
        recommendations=_StubRecommendations(),
        commercial=_StubCommercial(),
        demands=_StubDemands(),
    )
    result = await interactor.summary()
    assert result.member_total == 42
    assert result.member_new_this_month == 3
    assert result.area_count == 1742
    assert result.latest_quarter == "20251"
    assert result.recommendation_total == 100
    assert result.recommendation_today == 5
    assert result.monthly[0].month == "2026-07"
    assert result.top_categories[0].category == "카페"
    assert result.stock_demands[0].ticker == "NVDA"


async def test_데이터셋이_비어도_기본값으로_동작한다():
    class _Empty:
        async def get_dataset_stats(self):
            return []

    interactor = DashboardInteractor(
        members=_StubMembers(),
        recommendations=_StubRecommendations(),
        commercial=_Empty(),
        demands=_StubDemands(),
    )
    result = await interactor.summary()
    assert result.area_count == 0
    assert result.latest_quarter is None
