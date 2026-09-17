from __future__ import annotations

from hub.app.dtos.area_fitness_dto import AreaFitnessInfo, FitnessComponentInfo, FitnessDiagnosisInfo
from hub.app.ports.output.area_fitness_port import AreaFitnessPort
from market.app.dtos.area_fitness_dto import AreaFitnessQuery
from market.app.ports.input.area_fitness_use_case import AreaFitnessUseCase


class AreaFitnessGateway(AreaFitnessPort):
    """허브 AreaFitnessPort 구현 — area_fitness 인터랙터에 위임하고 View를 계약 DTO로 옮긴다."""

    def __init__(self, use_case: AreaFitnessUseCase) -> None:
        self._use_case = use_case

    async def evaluate(self, trdar_code: int, service_code: str) -> AreaFitnessInfo | None:
        view = await self._use_case.evaluate(AreaFitnessQuery(trdar_code=trdar_code, service_code=service_code))
        if view is None:
            return None
        return AreaFitnessInfo(
            trdar_code=view.trdar_code, trdar_name=view.trdar_name, service_code=view.service_code,
            service_name=view.service_name, year_quarter=view.year_quarter, total_score=view.total_score,
            components=tuple(FitnessComponentInfo(c.key, c.label, c.score, c.weight) for c in view.components),
            diagnoses=tuple(FitnessDiagnosisInfo(d.tone, d.message) for d in view.diagnoses),
            observed_ticket_price=view.observed_ticket_price,
            observed_similar_store_count=view.observed_similar_store_count,
            has_sales=view.has_sales, has_store=view.has_store,
        )
