from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from game.adapter.outbound.orm.game_ledger_orm import GameLedgerOrm
from game.adapter.outbound.orm.game_quarter_settlement_orm import GameQuarterSettlementOrm
from game.adapter.outbound.orm.game_store_decision_orm import GameStoreDecisionOrm
from game.adapter.outbound.orm.game_store_orm import GameStoreOrm
from game.adapter.outbound.orm.game_wallet_orm import GameWalletOrm
from game.app.dtos.store_dto import SettlementRecord, StoreDecisionRecord, StoreRecord
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
            # 앵커는 창업일 직전이다 — 0으로 두면 '0일차까지 정산됨'과 구분되지 않는다
            settled_through_day=opened_game_day - 1,
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

    async def add_decision(
        self,
        *,
        user_id: int,
        store_id: int,
        epoch_id: int,
        effective_from_day: int,
        price_factor: float,
        staff_count: int,
        facility_score: int,
        interior_cost_krw: int,
    ) -> StoreRecord:
        store = await self._locked_open_store(user_id, store_id, epoch_id)
        payload = {
            "price_factor": price_factor,
            "staff_count": staff_count,
            "facility_score": facility_score,
        }
        self._session.add(
            GameStoreDecisionOrm(
                store_id=store.id,
                effective_from_day=effective_from_day,
                payload=payload,
                epoch_id=epoch_id,
            )
        )
        if interior_cost_krw:
            # 인테리어는 회수되지 않는 지출이라 가게 원가에도 누적한다
            store.interior_krw += interior_cost_krw
            await self._move_cash(
                user_id=user_id,
                epoch_id=epoch_id,
                game_day=effective_from_day,
                amount_krw=-interior_cost_krw,
                ref_id=store.id,
            )
        await self._session.commit()
        return await self._with_decisions(store)

    async def close_store(
        self,
        *,
        user_id: int,
        store_id: int,
        epoch_id: int,
        closed_game_day: int,
        deposit_refund_krw: int,
    ) -> StoreRecord:
        store = await self._locked_open_store(user_id, store_id, epoch_id)
        store.status = "closed"
        store.closed_game_day = closed_game_day
        if deposit_refund_krw:
            await self._move_cash(
                user_id=user_id,
                epoch_id=epoch_id,
                game_day=closed_game_day,
                amount_krw=deposit_refund_krw,
                ref_id=store.id,
            )
        await self._session.commit()
        return await self._with_decisions(store)

    async def _locked_open_store(
        self, user_id: int, store_id: int, epoch_id: int
    ) -> GameStoreOrm:
        """영업 중인 내 가게를 잠그고 가져온다. 동시 요청은 두 번째가 여기서 걸린다."""
        store = await self._session.scalar(
            select(GameStoreOrm)
            .where(
                GameStoreOrm.id == store_id,
                GameStoreOrm.user_id == user_id,  # 남의 가게 차단
                GameStoreOrm.epoch_id == epoch_id,
                GameStoreOrm.status == "open",
            )
            .with_for_update()
        )
        if store is None:
            raise LookupError("영업 중인 가게가 없습니다")
        return store

    async def _move_cash(
        self, *, user_id: int, epoch_id: int, game_day: int, amount_krw: int, ref_id: int
    ) -> None:
        """지갑 증감 + 원장 기록. 둘은 항상 함께여야 불변식(SUM(ledger)==cash)이 유지된다."""
        wallet = await self._session.scalar(
            select(GameWalletOrm)
            .where(GameWalletOrm.user_id == user_id, GameWalletOrm.epoch_id == epoch_id)
            .with_for_update()
        )
        if wallet is None:
            raise LookupError("지갑이 없습니다")
        wallet.cash_krw += amount_krw
        self._session.add(
            GameLedgerOrm(
                user_id=user_id,
                game_day=game_day,
                source="store",
                amount_krw=amount_krw,
                ref_type="store",
                ref_id=ref_id,
                epoch_id=epoch_id,
            )
        )

    async def list_settlements(
        self, user_id: int, epoch_id: int
    ) -> tuple[SettlementRecord, ...]:
        rows = (
            await self._session.scalars(
                select(GameQuarterSettlementOrm)
                .join(GameStoreOrm, GameStoreOrm.id == GameQuarterSettlementOrm.store_id)
                .where(
                    GameStoreOrm.user_id == user_id,
                    GameQuarterSettlementOrm.epoch_id == epoch_id,
                )
                .order_by(
                    GameQuarterSettlementOrm.game_quarter, GameQuarterSettlementOrm.store_id
                )
            )
        ).all()
        return tuple(
            SettlementRecord(
                store_id=r.store_id,
                game_quarter=r.game_quarter,
                days_counted=r.days_counted,
                total_sales_krw=r.total_sales_krw,
                total_rent_krw=r.total_rent_krw,
                total_labor_krw=r.total_labor_krw,
                total_cogs_krw=r.total_cogs_krw,
                total_utility_krw=r.total_utility_krw,
                profit_krw=r.profit_krw,
                payload=r.payload or {},
            )
            for r in rows
        )

    async def record_settlement(
        self,
        *,
        user_id: int,
        epoch_id: int,
        store_id: int,
        settlement: SettlementRecord,
        settled_through_day: int,
        game_day: int,
    ) -> None:
        store = await self._session.scalar(
            select(GameStoreOrm)
            .where(GameStoreOrm.id == store_id, GameStoreOrm.user_id == user_id)
            .with_for_update()
        )
        if store is None:
            raise LookupError("가게가 없습니다")
        if store.settled_through_day >= settled_through_day:
            return  # 다른 요청이 먼저 정산했다 — 지연 실행이라 동시 조회가 겹칠 수 있다

        wallet = await self._session.scalar(
            select(GameWalletOrm)
            .where(GameWalletOrm.user_id == user_id, GameWalletOrm.epoch_id == epoch_id)
            .with_for_update()
        )
        if wallet is None:
            raise LookupError("지갑이 없습니다")

        self._session.add(
            GameQuarterSettlementOrm(
                store_id=store_id,
                game_quarter=settlement.game_quarter,
                days_counted=settlement.days_counted,
                total_sales_krw=settlement.total_sales_krw,
                total_rent_krw=settlement.total_rent_krw,
                total_labor_krw=settlement.total_labor_krw,
                total_cogs_krw=settlement.total_cogs_krw,
                total_utility_krw=settlement.total_utility_krw,
                profit_krw=settlement.profit_krw,
                payload=settlement.payload,
                epoch_id=epoch_id,
            )
        )
        # 손실이 나도 지갑은 음수가 되지 않는다 — 파산 없음(game-harness §2)
        applied = max(settlement.profit_krw, -wallet.cash_krw)
        wallet.cash_krw += applied
        store.settled_through_day = settled_through_day
        self._session.add(
            GameLedgerOrm(
                user_id=user_id,
                game_day=game_day,
                source="settlement",
                amount_krw=applied,
                ref_type="store",
                ref_id=store_id,
                epoch_id=epoch_id,
            )
        )
        await self._session.commit()

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
            settled_through_day=store.settled_through_day,
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
