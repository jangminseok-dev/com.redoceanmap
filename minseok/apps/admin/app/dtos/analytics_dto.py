from __future__ import annotations

from dataclasses import dataclass

from hub.app.dtos.area_backtest_report_dto import AreaBacktestReportInfo
from hub.app.dtos.forecast_refit_dto import RefitReportInfo, SignalConfigInfo
from hub.app.dtos.forecast_snapshot_dto import ForecastAccuracyReport
from hub.app.dtos.news_event_study_dto import NewsEventStudyInfo


@dataclass(frozen=True)
class ForecastReportResponse:
    report: ForecastAccuracyReport


@dataclass(frozen=True)
class ForecastRefitResponse:
    """재적합 화면 1회 호출용 — 최신 리포트 + 판정 조합 이력을 한 응답에."""

    report: RefitReportInfo | None       # 재적합 실행 이력이 없으면 None
    history: list[SignalConfigInfo]


@dataclass(frozen=True)
class MarketBacktestResponse:
    report: AreaBacktestReportInfo | None  # 백테스트 실행 이력이 없으면 None


@dataclass(frozen=True)
class NewsEventStudyResponse:
    report: NewsEventStudyInfo | None  # 연구 실행 이력이 없으면 None
