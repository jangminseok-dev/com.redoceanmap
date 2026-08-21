from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.analytics_dto import (
    ForecastRefitResponse,
    ForecastReportResponse,
    MarketBacktestResponse,
    NewsEventStudyResponse,
)


class AnalyticsUseCase(ABC):
    """어드민 분석 검증 유스케이스 — 예측 채점 현황·상권 백테스트 리포트."""

    @abstractmethod
    async def forecast_report(self, horizon: int | None, limit: int) -> ForecastReportResponse:
        """주식 예측 스냅샷 적중률 요약 + 최근 목록."""
        ...

    @abstractmethod
    async def market_backtest_report(self) -> MarketBacktestResponse:
        """상권 점수 워크포워드 백테스트 최신 리포트 — 없으면 report=None."""
        ...

    @abstractmethod
    async def news_event_study(self) -> NewsEventStudyResponse:
        """뉴스 이벤트 사후 수익률 최신 연구 리포트 — 없으면 report=None."""
        ...

    @abstractmethod
    async def forecast_refit(self) -> ForecastRefitResponse:
        """가중치 재적합 최신 리포트 + 판정 조합 이력 — 실행 전이면 report=None."""
        ...
