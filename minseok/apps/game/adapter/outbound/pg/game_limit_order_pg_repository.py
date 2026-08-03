from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from game.adapter.outbound.orm.game_limit_order_orm import GameLimitOrderOrm
from game.app.ports.output.game_limit_order_repository import (
    GameLimitOrderRepository,
    LimitOrderRecord,
)

_CLOSED_STATUSES = ("filled", "cancelled", "expired")


def _to_record(row: GameLimitOrderOrm) -> LimitOrderRecord:
    return LimitOrderRecord(
        id=row.id,
        user_id=row.user_id,
        kind=row.kind,
        symbol=row.symbol,
        side=row.side,
        position_id=row.position_id,
        trigger=row.trigger,
        limit_price_krw=row.limit_price_krw,
        quantity=row.quantity,
        leverage=row.leverage,
        placed_tick=row.placed_tick,
        expires_tick=row.expires_tick,
        status=row.status,
        filled_tick=row.filled_tick,
        filled_price_krw=row.filled_price_krw,
        reserved_cash_krw=row.reserved_cash_krw,
    )


class GameLimitOrderPgRepository(GameLimitOrderRepository):
    """지정가 주문 영속.

    상태 전이는 전부 `status == 'pending'` 조건부 UPDATE다 — 동시 요청 둘이 같은 주문을
    체결시키는 것을 DB가 막고, 두 번째는 `LookupError`로 돌아온다(지연 정산 루프가 삼킨다).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def place(
        self,
        user_id: int,
        epoch_id: int,
        kind: str,
        symbol: str,
        side: str,
        trigger: str,
        limit_price_krw: int,
        quantity: int,
        placed_tick: int,
        expires_tick: int,
        leverage: int = 1,
        position_id: int | None = None,
        reserved_cash_krw: int = 0,
    ) -> LimitOrderRecord:
        row = GameLimitOrderOrm(
            user_id=user_id,
            epoch_id=epoch_id,
            kind=kind,
            symbol=symbol,
            side=side,
            position_id=position_id,
            trigger=trigger,
            limit_price_krw=limit_price_krw,
            quantity=quantity,
            leverage=leverage,
            placed_tick=placed_tick,
            expires_tick=expires_tick,
            status="pending",
            reserved_cash_krw=reserved_cash_krw,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_record(row)

    async def list_pending(self, user_id: int, epoch_id: int) -> tuple[LimitOrderRecord, ...]:
        rows = await self._session.scalars(
            select(GameLimitOrderOrm)
            .where(
                GameLimitOrderOrm.user_id == user_id,
                GameLimitOrderOrm.epoch_id == epoch_id,
                GameLimitOrderOrm.status == "pending",
            )
            .order_by(GameLimitOrderOrm.id)
        )
        return tuple(_to_record(r) for r in rows)

    async def list_recent(
        self, user_id: int, epoch_id: int, limit: int = 20
    ) -> tuple[LimitOrderRecord, ...]:
        rows = await self._session.scalars(
            select(GameLimitOrderOrm)
            .where(
                GameLimitOrderOrm.user_id == user_id,
                GameLimitOrderOrm.epoch_id == epoch_id,
                GameLimitOrderOrm.status.in_(_CLOSED_STATUSES),
            )
            .order_by(GameLimitOrderOrm.id.desc())
            .limit(limit)
        )
        return tuple(_to_record(r) for r in rows)

    async def find(self, user_id: int, order_id: int) -> LimitOrderRecord | None:
        row = await self._session.scalar(
            select(GameLimitOrderOrm).where(
                GameLimitOrderOrm.id == order_id, GameLimitOrderOrm.user_id == user_id
            )
        )
        return _to_record(row) if row else None

    async def mark_filled(self, order_id: int, filled_tick: int, filled_price_krw: int) -> None:
        await self._transition(
            order_id,
            status="filled",
            filled_tick=filled_tick,
            filled_price_krw=filled_price_krw,
        )

    async def mark_closed(self, order_id: int, status: str) -> None:
        if status not in ("cancelled", "expired"):
            raise ValueError(f"종료 상태가 아닙니다: {status}")
        await self._transition(order_id, status=status)

    async def cancel_for_position(
        self, position_id: int, except_order_id: int | None = None
    ) -> int:
        stmt = (
            update(GameLimitOrderOrm)
            .where(
                GameLimitOrderOrm.position_id == position_id,
                GameLimitOrderOrm.status == "pending",
            )
            .values(status="cancelled")
        )
        if except_order_id is not None:
            stmt = stmt.where(GameLimitOrderOrm.id != except_order_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or 0

    async def extend(self, order_id: int, expires_tick: int) -> None:
        result = await self._session.execute(
            update(GameLimitOrderOrm)
            .where(GameLimitOrderOrm.id == order_id, GameLimitOrderOrm.status == "pending")
            .values(expires_tick=expires_tick)
        )
        await self._session.commit()
        if not result.rowcount:
            raise LookupError(f"대기 중인 주문이 아닙니다: id={order_id}")

    async def _transition(self, order_id: int, **values) -> None:
        result = await self._session.execute(
            update(GameLimitOrderOrm)
            .where(GameLimitOrderOrm.id == order_id, GameLimitOrderOrm.status == "pending")
            .values(**values)
        )
        await self._session.commit()
        if not result.rowcount:
            raise LookupError(f"대기 중인 주문이 아닙니다: id={order_id}")
