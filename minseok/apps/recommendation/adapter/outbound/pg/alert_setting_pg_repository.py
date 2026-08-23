from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation.adapter.outbound.orm.alert_orm import AlertSettingOrm
from recommendation.app.ports.output.alert_setting_repository import AlertSettingRepositoryPort


class AlertSettingPgRepository(AlertSettingRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_user(self, user_id: int) -> bool | None:
        return (await self._session.execute(
            select(AlertSettingOrm.email_alerts).where(AlertSettingOrm.user_id == user_id)
        )).scalar_one_or_none()

    async def upsert(self, user_id: int, email_alerts: bool) -> None:
        await self._session.execute(
            pg_insert(AlertSettingOrm)
            .values(user_id=user_id, email_alerts=email_alerts)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"email_alerts": email_alerts, "updated_at": func.now()},
            )
        )
        await self._session.commit()
