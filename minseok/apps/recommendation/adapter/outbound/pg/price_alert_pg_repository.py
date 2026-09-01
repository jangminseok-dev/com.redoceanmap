from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation.adapter.outbound.orm.price_alert_orm import PriceAlertOrm
from recommendation.app.dtos.price_alert_dto import PriceAlertDraft, StoredPriceAlert
from recommendation.app.ports.output.price_alert_repository import PriceAlertRepositoryPort


def _to_stored(row: PriceAlertOrm) -> StoredPriceAlert:
    return StoredPriceAlert(
        id=row.id, ticker=row.ticker, target_price=row.target_price,
        direction=row.direction, active=row.active,
        triggered_at=row.triggered_at, created_at=row.created_at,
    )


class PriceAlertPgRepository(PriceAlertRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: int) -> list[StoredPriceAlert]:
        rows = (await self._session.execute(
            select(PriceAlertOrm)
            .where(PriceAlertOrm.user_id == user_id)
            .order_by(PriceAlertOrm.id.desc())
        )).scalars().all()
        return [_to_stored(r) for r in rows]

    async def count_active(self, user_id: int) -> int:
        return (await self._session.execute(
            select(func.count()).select_from(PriceAlertOrm)
            .where(PriceAlertOrm.user_id == user_id, PriceAlertOrm.active)
        )).scalar_one()

    async def add(self, draft: PriceAlertDraft) -> StoredPriceAlert:
        row = PriceAlertOrm(
            user_id=draft.user_id, ticker=draft.ticker,
            target_price=draft.target_price, direction=draft.direction,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_stored(row)

    async def delete(self, user_id: int, alert_id: int) -> bool:
        result = await self._session.execute(
            delete(PriceAlertOrm).where(
                PriceAlertOrm.id == alert_id, PriceAlertOrm.user_id == user_id,
            )
        )
        await self._session.commit()
        return result.rowcount > 0
