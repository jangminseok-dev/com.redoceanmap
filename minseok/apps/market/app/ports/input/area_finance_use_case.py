from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_finance_dto import AreaFinanceQuery, AreaFinanceView


class AreaFinanceUseCase(ABC):
    """창업 재무 계산 — 상권·업종 + 사용자 입력 → BEP·부족 자금·runway."""

    @abstractmethod
    async def calculate(self, query: AreaFinanceQuery) -> AreaFinanceView | None:
        """상권·업종이 없거나 월세를 어디서도 못 구하면 None(HTTP 변환은 라우터 몫)."""
        ...
