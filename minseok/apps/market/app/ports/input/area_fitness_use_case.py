from __future__ import annotations

from abc import ABC, abstractmethod

from market.app.dtos.area_fitness_dto import AreaFitnessQuery, AreaFitnessView


class AreaFitnessUseCase(ABC):
    """입지 적합도 — 상권·업종 조합의 4축 판정 + 진단 문장."""

    @abstractmethod
    async def evaluate(self, query: AreaFitnessQuery) -> AreaFitnessView | None:
        """자료(상권·업종·적재 분기)가 없으면 None(HTTP 변환은 라우터 몫)."""
        ...
