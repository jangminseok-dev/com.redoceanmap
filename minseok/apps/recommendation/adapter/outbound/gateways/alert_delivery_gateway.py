from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.alert_delivery_dto import DeliveredSignal
from hub.app.ports.output.alert_delivery_port import AlertDeliveryPort
from recommendation.adapter.outbound.orm.alert_orm import AlertDeliveryOrm


class AlertDeliveryGateway(AlertDeliveryPort):
    """허브의 AlertDeliveryPort를 recommendation(스포크)이 구현한다 — 직접 조회 선례."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def last_signals(self) -> list[DeliveredSignal]:
        rows = (await self._session.execute(
            select(AlertDeliveryOrm.user_id, AlertDeliveryOrm.ticker, AlertDeliveryOrm.direction)
        )).all()
        return [
            DeliveredSignal(user_id=user_id, ticker=ticker, direction=direction)
            for user_id, ticker, direction in rows
        ]

    async def replace(self, signals: list[DeliveredSignal]) -> None:
        # 전량 스캔 전제의 전체 교체 — 부분 갱신을 흉내내지 않는다(계약 그대로)
        await self._session.execute(delete(AlertDeliveryOrm))
        self._session.add_all([
            AlertDeliveryOrm(user_id=s.user_id, ticker=s.ticker, direction=s.direction)
            for s in signals
        ])
        await self._session.commit()
