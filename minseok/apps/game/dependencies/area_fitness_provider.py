from __future__ import annotations

from fastapi import Depends

from game.app.ports.input.area_fitness_use_case import AreaFitnessUseCase
from game.app.use_cases.area_fitness_interactor import AreaFitnessInteractor
from hub.app.ports.output.area_demand_profile_port import AreaDemandProfilePort
from hub.dependencies.area_demand_profile_provider import get_area_demand_profile_port


def get_area_fitness_use_case(
    profiles: AreaDemandProfilePort = Depends(get_area_demand_profile_port),
) -> AreaFitnessUseCase:
    """허브 스텁 프로바이더를 주입받는다 — main.py가 market 게이트웨이로 치환한다."""
    return AreaFitnessInteractor(profiles=profiles)
