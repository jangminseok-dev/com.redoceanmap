from __future__ import annotations

from admin.app.dtos.analytics_dto import (
    ForecastReportResponse,
    MarketBacktestResponse,
    NewsEventStudyResponse,
)
from admin.app.ports.input.analytics_use_case import AnalyticsUseCase
from hub.app.ports.output.area_backtest_report_port import AreaBacktestReportPort
from hub.app.ports.output.forecast_snapshot_port import ForecastSnapshotPort
from hub.app.ports.output.news_event_study_port import NewsEventStudyPort


class AnalyticsInteractor(AnalyticsUseCase):
    """어드민 분석 검증 대장 — 허브 포트 3종을 소비해 화면용 리포트를 만든다."""

    def __init__(
        self,
        forecasts: ForecastSnapshotPort,
        area_backtests: AreaBacktestReportPort,
        news_events: NewsEventStudyPort,
    ) -> None:
        self._forecasts = forecasts
        self._area_backtests = area_backtests
        self._news_events = news_events

    async def forecast_report(self, horizon: int | None, limit: int) -> ForecastReportResponse:
        report = await self._forecasts.accuracy_report(horizon=horizon, recent_limit=limit)
        return ForecastReportResponse(report=report)

    async def market_backtest_report(self) -> MarketBacktestResponse:
        return MarketBacktestResponse(report=await self._area_backtests.latest())

    async def news_event_study(self) -> NewsEventStudyResponse:
        return NewsEventStudyResponse(report=await self._news_events.latest())
