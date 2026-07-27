from __future__ import annotations

from fastapi import Depends

from admin.app.ports.input.analytics_use_case import AnalyticsUseCase
from admin.app.use_cases.analytics_interactor import AnalyticsInteractor
from hub.app.ports.output.area_backtest_report_port import AreaBacktestReportPort
from hub.app.ports.output.forecast_snapshot_port import ForecastSnapshotPort
from hub.app.ports.output.news_event_study_port import NewsEventStudyPort
from hub.dependencies.area_backtest_report_provider import get_area_backtest_report_port
from hub.dependencies.forecast_snapshot_provider import get_forecast_snapshot_port
from hub.dependencies.news_event_study_provider import get_news_event_study_port


def get_analytics_use_case(
    forecasts: ForecastSnapshotPort = Depends(get_forecast_snapshot_port),
    area_backtests: AreaBacktestReportPort = Depends(get_area_backtest_report_port),
    news_events: NewsEventStudyPort = Depends(get_news_event_study_port),
) -> AnalyticsUseCase:
    return AnalyticsInteractor(
        forecasts=forecasts, area_backtests=area_backtests, news_events=news_events
    )
