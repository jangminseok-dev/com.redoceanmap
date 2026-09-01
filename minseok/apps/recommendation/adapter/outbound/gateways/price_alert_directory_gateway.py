from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.price_alert_scan_dto import ActivePriceAlert
from hub.app.ports.output.price_alert_directory_port import PriceAlertDirectoryPort
from recommendation.adapter.outbound.orm.alert_orm import AlertSettingOrm
from recommendation.adapter.outbound.orm.price_alert_orm import PriceAlertOrm


class PriceAlertDirectoryGateway(PriceAlertDirectoryPort):
    """허브의 PriceAlertDirectoryPort를 recommendation(스포크)이 구현한다.

    발송 대상 열람 의미론(BookmarkDirectoryGateway 선례): 알림 수신을 끈 회원
    (user_alert_settings.email_alerts=false)은 active_alerts에서 제외한다.
    행이 없는 회원은 기본 수신(포함).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_alerts(self) -> list[ActivePriceAlert]:
        rows = (await self._session.execute(
            select(
                PriceAlertOrm.id, PriceAlertOrm.user_id, PriceAlertOrm.ticker,
                PriceAlertOrm.target_price, PriceAlertOrm.direction,
            )
            .outerjoin(AlertSettingOrm, AlertSettingOrm.user_id == PriceAlertOrm.user_id)
            .where(
                PriceAlertOrm.active,
                # 설정 행이 없으면(NULL) 기본 수신 — false 명시자만 제외
                AlertSettingOrm.email_alerts.isnot(False),
            )
            .order_by(PriceAlertOrm.user_id, PriceAlertOrm.id)
        )).all()
        return [
            ActivePriceAlert(
                alert_id=alert_id, user_id=user_id, ticker=ticker,
                target_price=target_price, direction=direction,
            )
            for alert_id, user_id, ticker, target_price, direction in rows
        ]

    async def mark_triggered(self, alert_ids: list[int]) -> None:
        if not alert_ids:
            return
        await self._session.execute(
            update(PriceAlertOrm)
            .where(PriceAlertOrm.id.in_(alert_ids))
            .values(active=False, triggered_at=func.now())
        )
        await self._session.commit()

    async def telegram_chat_ids(self, user_ids: list[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rows = (await self._session.execute(
            select(AlertSettingOrm.user_id, AlertSettingOrm.telegram_chat_id)
            .where(
                AlertSettingOrm.user_id.in_(user_ids),
                AlertSettingOrm.telegram_chat_id.is_not(None),
            )
        )).all()
        return {user_id: chat_id for user_id, chat_id in rows if chat_id}
