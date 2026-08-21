from __future__ import annotations

from abc import ABC, abstractmethod

from stock.app.dtos.forecast_refit_dto import RefitReportView


class RefitReportRepositoryPort(ABC):
    """재적합 리포트 영속 아웃바운드 포트 — 실행당 1행(params + payload)."""

    @abstractmethod
    async def save(self, params: dict, payload: dict) -> None:
        """실행 결과를 1행 추가한다(게이트 미달 리포트도 저장 — 표본 축적 경과 관측용)."""
        ...

    @abstractmethod
    async def latest(self) -> RefitReportView | None:
        """최신 리포트 1건 — 없으면 None."""
        ...
