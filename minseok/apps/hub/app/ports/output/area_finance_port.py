from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.area_finance_dto import AreaFinancePlanInfo, AreaFinanceRequest


class AreaFinancePort(ABC):
    """허브가 스포크에 위임하는 창업 재무 계산 추상 — 구현은 market 게이트웨이, 소비는 chat."""

    @abstractmethod
    async def plan(self, request: AreaFinanceRequest) -> AreaFinancePlanInfo | None:
        """상권·업종이 없거나 월세를 못 구하면 None(소비자가 되묻는다)."""
        ...
