from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.area_fitness_dto import AreaFitnessQuery, AreaFitnessView


class AreaFitnessUseCase(ABC):
    """입지 적합도 미리보기 — 창업하기 전에 "여기에 이걸 열면 어떻게 되는가"를 본다."""

    @abstractmethod
    async def preview(self, query: AreaFitnessQuery) -> AreaFitnessView:
        """상권·업종 조합의 적합도와 진단. 자료가 없으면 앱 예외."""
        ...
