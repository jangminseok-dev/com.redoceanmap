from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.area_fitness_dto import AreaFitnessInfo


class AreaFitnessPort(ABC):
    """허브가 스포크에 위임하는 입지 적합도 조회 추상 — 구현은 market 게이트웨이, 소비는 chat 비교 경로."""

    @abstractmethod
    async def evaluate(self, trdar_code: int, service_code: str) -> AreaFitnessInfo | None:
        """상권×업종 적합도 — 자료(상권·업종·적재 분기)가 없으면 None."""
        ...
