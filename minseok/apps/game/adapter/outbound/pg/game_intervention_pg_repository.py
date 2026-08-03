from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from game.adapter.outbound.orm.game_price_intervention_orm import GamePriceInterventionOrm
from game.app.ports.output.game_intervention_repository import GameInterventionRepository
from game.domain.market.price_intervention import PriceIntervention


def _to_domain(row: GamePriceInterventionOrm) -> PriceIntervention:
    return PriceIntervention(
        id=row.id,
        epoch_id=row.epoch_id,
        scope=row.scope,
        target=row.target,
        target_name=row.target_name,
        from_tick=row.from_tick,
        shock_pct=row.shock_pct,
        drift_pct_per_day=row.drift_pct_per_day,
        duration_days=row.duration_days,
        headline=row.headline,
        note=row.note,
    )


class GameInterventionPgRepository(GameInterventionRepository):
    """개입 영속. 조회는 `(epoch_id, from_tick)` 복합 인덱스를 그대로 탄다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_in_window(
        self, epoch_id: int, tick: int, window_ticks: int
    ) -> tuple[PriceIntervention, ...]:
        rows = await self._session.scalars(
            select(GamePriceInterventionOrm)
            .where(
                GamePriceInterventionOrm.epoch_id == epoch_id,
                GamePriceInterventionOrm.from_tick <= tick,
                GamePriceInterventionOrm.from_tick >= tick - window_ticks,
            )
            .order_by(GamePriceInterventionOrm.from_tick)
        )
        return tuple(_to_domain(r) for r in rows)

    async def create(
        self,
        epoch_id: int,
        scope: str,
        target: str,
        target_name: str,
        from_tick: int,
        shock_pct: float,
        drift_pct_per_day: float,
        duration_days: int,
        headline: str,
        note: str | None,
        created_by: int,
    ) -> PriceIntervention:
        row = GamePriceInterventionOrm(
            epoch_id=epoch_id,
            scope=scope,
            target=target,
            target_name=target_name,
            from_tick=from_tick,
            shock_pct=shock_pct,
            drift_pct_per_day=drift_pct_per_day,
            duration_days=duration_days,
            headline=headline,
            note=note,
            created_by=created_by,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_domain(row)

    async def list_recent(self, epoch_id: int, limit: int) -> tuple[PriceIntervention, ...]:
        rows = await self._session.scalars(
            select(GamePriceInterventionOrm)
            .where(GamePriceInterventionOrm.epoch_id == epoch_id)
            .order_by(GamePriceInterventionOrm.id.desc())
            .limit(limit)
        )
        return tuple(_to_domain(r) for r in rows)
