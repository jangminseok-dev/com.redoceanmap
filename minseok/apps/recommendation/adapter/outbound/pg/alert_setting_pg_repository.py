from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation.adapter.outbound.orm.alert_orm import AlertSettingOrm
from recommendation.app.ports.output.alert_setting_repository import (
    AlertSettingRepositoryPort,
    StoredAlertSetting,
)


class AlertSettingPgRepository(AlertSettingRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_user(self, user_id: int) -> StoredAlertSetting | None:
        row = (await self._session.execute(
            select(AlertSettingOrm.email_alerts, AlertSettingOrm.telegram_chat_id)
            .where(AlertSettingOrm.user_id == user_id)
        )).one_or_none()
        if row is None:
            return None
        return StoredAlertSetting(email_alerts=row[0], telegram_chat_id=row[1])

    async def upsert(
        self, user_id: int, email_alerts: bool, telegram_chat_id: str | None
    ) -> None:
        await self._session.execute(
            pg_insert(AlertSettingOrm)
            .values(
                user_id=user_id, email_alerts=email_alerts,
                telegram_chat_id=telegram_chat_id,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "email_alerts": email_alerts,
                    "telegram_chat_id": telegram_chat_id,
                    "updated_at": func.now(),
                },
            )
        )
        await self._session.commit()
