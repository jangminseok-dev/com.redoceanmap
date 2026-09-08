from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.area_demand_profile_dto import AreaDemandProfile
from hub.app.ports.output.area_demand_profile_port import AreaDemandProfilePort
from market.adapter.outbound.pg.area_demand_profile_pg_repository import (
    AreaDemandProfilePgRepository,
)


class AreaDemandProfileGateway(AreaDemandProfilePort):
    """허브의 AreaDemandProfilePort를 market(스포크)이 구현한다.

    조회 본문은 market 내부 리포지토리(`AreaDemandProfilePgRepository`)로 옮겼다 — 입지 적합도가
    market 슬라이스가 되면서(2026-09) 허브 계약은 game 스포크만 소비한다. game 삭제와 함께 이
    파일·허브 포트도 지운다(GAME_SUNSET_PAPER_TRADING_PLAN 2단계).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repo = AreaDemandProfilePgRepository(session=session)

    async def get_demand_profile(
        self, trdar_code: int, service_code: str, year_quarter: int
    ) -> AreaDemandProfile | None:
        profile = await self._repo.get_demand_profile(trdar_code, service_code, year_quarter)
        return AreaDemandProfile(**asdict(profile)) if profile is not None else None
