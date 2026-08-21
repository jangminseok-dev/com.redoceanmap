from __future__ import annotations

from abc import ABC, abstractmethod

from stock.app.dtos.forecast_refit_dto import RefitReportView, RefitRunResult
from stock.app.dtos.signal_config_dto import ConfigHistoryRow


class ForecastRefitUseCase(ABC):
    """가중치 재적합 유스케이스 — 실행(주 1회 배치)·최신 리포트·조합 이력 조회."""

    @abstractmethod
    async def run(self, promote: bool) -> RefitRunResult:
        """채점 표본으로 후보를 재채점한다. promote=False면 리포트만 남긴다(dry-run)."""
        ...

    @abstractmethod
    async def latest(self) -> RefitReportView | None:
        """최신 재적합 리포트 1건 — 실행 이력이 없으면 None."""
        ...

    @abstractmethod
    async def config_history(self) -> list[ConfigHistoryRow]:
        """판정 조합 이력(최신순) — 어드민 승격 이력 화면용."""
        ...
