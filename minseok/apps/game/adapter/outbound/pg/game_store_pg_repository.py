from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from game.adapter.outbound.orm.game_ledger_orm import GameLedgerOrm
from game.adapter.outbound.orm.game_store_decision_orm import GameStoreDecisionOrm
from game.adapter.outbound.orm.game_store_orm import GameStoreOrm
from game.adapter.outbound.orm.game_wallet_orm import GameWalletOrm
from game.app.dtos.store_dto import StoreDecisionRecord, StoreRecord
from game.app.ports.output.game_store_repository import GameStoreRepository


class GameStorePgRepository(GameStoreRepository):
    """가게 영속. 창업은 가게·결정·지갑·원장 **네 테이블을 한 커밋으로** 바꾼다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_store(
        self,
        *,
        user_id: int,
        epoch_id: int,
        trdar_code: int,
        service_code: str,
        opened_game_day: int,
        store_scale: float,
        deposit_krw: int,
        interior_krw: int,
        profile_snapshot: dict,
        decision: dict,
        cash_delta_krw: int,
    ) -> StoreRecord:
        wallet = await self._session.scalar(
            select(GameWalletOrm)
            .where(GameWalletOrm.user_id == user_id, GameWalletOrm.epoch_id == epoch_id)
            .with_for_update()
        )
        if wallet is None:
            raise LookupError("지갑이 없습니다")

        store = GameStoreOrm(
            user_id=user_id,
            trdar_code=trdar_code,
            service_code=service_code,
            opened_game_day=opened_game_day,
            closed_game_day=None,
            status="open",
            store_scale=store_scale,
            deposit_krw=deposit_krw,
            interior_krw=interior_krw,
            profile_snapshot=profile_snapshot,
            settled_through_day=0,
            epoch_id=epoch_id,
        )
        self._session.add(store)
        await self._session.flush()  # store.id 확보 — 결정·원장이 참조한다

        self._session.add(
            GameStoreDecisionOrm(
                store_id=store.id,
                effective_from_day=opened_game_day,
                payload=decision,
                epoch_id=epoch_id,
            )
        )
        wallet.cash_krw += cash_delta_krw
        self._session.add(
            GameLedgerOrm(
                user_id=user_id,
                game_day=opened_game_day,
                source="store",
                amount_krw=cash_delta_krw,
                ref_type="store",
                ref_id=store.id,
                epoch_id=epoch_id,
            )
        )
        await self._session.commit()
        return self._to_record(store, [decision | {"effective_from_day": opened_game_day}])

    async def list_stores(self, user_id: int, epoch_id: int) -> tuple[StoreRecord, ...]:
        stores = (
            await self._session.scalars(
                select(GameStoreOrm)
                .where(GameStoreOrm.user_id == user_id, GameStoreOrm.epoch_id == epoch_id)
                .order_by(GameStoreOrm.id)
            )
        ).all()
        return tuple([await self._with_decisions(s) for s in stores])

    async def find_store(
        self, user_id: int, store_id: int, epoch_id: int
    ) -> StoreRecord | None:
        store = await self._session.scalar(
            select(GameStoreOrm).where(
                GameStoreOrm.id == store_id,
                GameStoreOrm.user_id == user_id,  # 남의 가게 조회 차단
                GameStoreOrm.epoch_id == epoch_id,
            )
        )
        if store is None:
            return None
        return await self._with_decisions(store)

    async def _with_decisions(self, store: GameStoreOrm) -> StoreRecord:
        rows = (
            await self._session.scalars(
                select(GameStoreDecisionOrm)
                .where(GameStoreDecisionOrm.store_id == store.id)
                .order_by(GameStoreDecisionOrm.effective_from_day)
            )
        ).all()
        decisions = [
            r.payload | {"effective_from_day": r.effective_from_day} for r in rows
        ]
        return self._to_record(store, decisions)

    @staticmethod
    def _to_record(store: GameStoreOrm, decisions: list[dict]) -> StoreRecord:
        snapshot = store.profile_snapshot or {}
        return StoreRecord(
            id=store.id,
            user_id=store.user_id,
            trdar_code=store.trdar_code,
            trdar_name=snapshot.get("trdar_name", ""),
            service_code=store.service_code,
            service_name=snapshot.get("service_name", ""),
            opened_game_day=store.opened_game_day,
            closed_game_day=store.closed_game_day,
            status=store.status,
            store_scale=store.store_scale,
            deposit_krw=store.deposit_krw,
            interior_krw=store.interior_krw,
            observed_sales_per_store=int(snapshot.get("observed_sales_per_store", 0)),
            observed_ticket_price=int(snapshot.get("observed_ticket_price", 1)),
            fitness=float(snapshot.get("fitness", 1.0)),
            rent_location_factor=float(snapshot.get("rent_location_factor", 1.0)),
            area_weekday_share=tuple(snapshot.get("area_weekday_share", ())),
            area_hour_share=tuple(snapshot.get("area_hour_share", ())),
            area_gender_share=tuple(snapshot.get("area_gender_share", ())),
            area_age_share=tuple(snapshot.get("area_age_share", ())),
            decisions=tuple(
                StoreDecisionRecord(
                    effective_from_day=int(d["effective_from_day"]),
                    price_factor=float(d.get("price_factor", 1.0)),
                    staff_count=int(d.get("staff_count", 1)),
                    facility_score=int(d.get("facility_score", 100)),
                )
                for d in decisions
            ),
        )
