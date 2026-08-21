from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.forecast_refit_dto import (
    RefitReportInfo,
    RefitRunOutcome,
    SignalConfigInfo,
)


class ForecastRefitPort(ABC):
    """허브가 스포크에 위임하는 가중치 재적합 추상 — 실행·최신 리포트·조합 이력.

    구현은 stock 게이트웨이. 자동화(주 1회 cron)가 run을 부르고, admin의 analytics
    인터랙터가 latest·config_history를 소비한다(ForecastSnapshotPort 선례 —
    자동화 트리거와 admin 조회를 한 계약에 담는다).
    """

    @abstractmethod
    async def run(self, promote: bool) -> RefitRunOutcome:
        """채점 표본으로 후보 조합을 재채점하고, promote면 게이트 통과 시 활성 교체."""
        ...

    @abstractmethod
    async def latest(self) -> RefitReportInfo | None:
        """최신 재적합 리포트 1건 — 실행 이력이 없으면 None."""
        ...

    @abstractmethod
    async def config_history(self) -> list[SignalConfigInfo]:
        """판정 조합 이력(최신순) — 활성 조합·과거 승격분."""
        ...
