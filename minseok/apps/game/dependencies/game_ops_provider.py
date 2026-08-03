from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from game.adapter.outbound.gateways.game_ops_gateway import GameOpsGateway
from game.adapter.outbound.pg.game_account_pg_repository import GameAccountPgRepository
from game.adapter.outbound.pg.game_intervention_pg_repository import (
    GameInterventionPgRepository,
)
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from hub.app.ports.output.game_ops_port import GameOpsPort


def get_game_ops_gateway(db: AsyncSession = Depends(get_db)) -> GameOpsPort:
    return GameOpsGateway(
        accounts=GameAccountPgRepository(session=db),
        interventions=GameInterventionPgRepository(session=db),
        clock=SystemGameClockAdapter(),
    )
