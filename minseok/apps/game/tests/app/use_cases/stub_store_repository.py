"""인메모리 가게 리포지토리 스텁. 원장까지 쌓아 불변식을 함께 검증한다."""
from __future__ import annotations

from game.app.dtos.store_dto import SettlementRecord, StoreDecisionRecord, StoreRecord


class StubStoreRepository:
    def __init__(self, accounts=None) -> None:
        self.stores: dict[int, dict] = {}
        self.settlements: list[SettlementRecord] = []
        self._next_id = 1
        self._accounts = accounts  # 지갑·원장을 함께 움직이려면 주입한다

    async def create_store(
        self,
        *,
        user_id,
        epoch_id,
        trdar_code,
        service_code,
        opened_game_day,
        store_scale,
        deposit_krw,
        interior_krw,
        profile_snapshot,
        decision,
        cash_delta_krw,
    ) -> StoreRecord:
        store_id = self._next_id
        self._next_id += 1
        self.stores[store_id] = {
            "id": store_id,
            "user_id": user_id,
            "epoch_id": epoch_id,
            "trdar_code": trdar_code,
            "service_code": service_code,
            "opened_game_day": opened_game_day,
            "closed_game_day": None,
            "status": "open",
            "store_scale": store_scale,
            "deposit_krw": deposit_krw,
            "interior_krw": interior_krw,
            "profile_snapshot": profile_snapshot,
            "decisions": [decision | {"effective_from_day": opened_game_day}],
            "settled_through_day": opened_game_day - 1,
        }
        if self._accounts is not None:
            self._accounts.wallets[user_id]["cash_krw"] += cash_delta_krw
            self._accounts.ledger.append(
                {"user_id": user_id, "source": "store", "amount_krw": cash_delta_krw}
            )
        return self._to_record(self.stores[store_id])

    async def list_stores(self, user_id, epoch_id) -> tuple[StoreRecord, ...]:
        return tuple(
            self._to_record(s)
            for s in self.stores.values()
            if s["user_id"] == user_id and s["epoch_id"] == epoch_id
        )

    async def find_store(self, user_id, store_id, epoch_id) -> StoreRecord | None:
        store = self.stores.get(store_id)
        if store is None or store["user_id"] != user_id or store["epoch_id"] != epoch_id:
            return None
        return self._to_record(store)

    # --- 운영 액션 (17단계) ------------------------------------------------

    async def add_decision(
        self,
        *,
        user_id,
        store_id,
        epoch_id,
        effective_from_day,
        price_factor,
        staff_count,
        facility_score,
        interior_cost_krw,
    ) -> StoreRecord:
        store = self.stores[store_id]
        store["decisions"].append(
            {
                "effective_from_day": effective_from_day,
                "price_factor": price_factor,
                "staff_count": staff_count,
                "facility_score": facility_score,
            }
        )
        if interior_cost_krw:
            store["interior_krw"] += interior_cost_krw
            self._move_cash(user_id, -interior_cost_krw)
        return self._to_record(store)

    async def close_store(
        self, *, user_id, store_id, epoch_id, closed_game_day, deposit_refund_krw
    ) -> StoreRecord:
        store = self.stores[store_id]
        store["status"] = "closed"
        store["closed_game_day"] = closed_game_day
        if deposit_refund_krw:
            self._move_cash(user_id, deposit_refund_krw)
        return self._to_record(store)

    def _move_cash(self, user_id: int, amount_krw: int) -> None:
        if self._accounts is None:
            return
        self._accounts.wallets[user_id]["cash_krw"] += amount_krw
        self._accounts.ledger.append(
            {"user_id": user_id, "source": "store", "amount_krw": amount_krw}
        )

    @staticmethod
    def _to_record(store: dict) -> StoreRecord:
        snapshot = store["profile_snapshot"]
        return StoreRecord(
            id=store["id"],
            user_id=store["user_id"],
            trdar_code=store["trdar_code"],
            trdar_name=snapshot.get("trdar_name", ""),
            service_code=store["service_code"],
            service_name=snapshot.get("service_name", ""),
            opened_game_day=store["opened_game_day"],
            closed_game_day=store["closed_game_day"],
            status=store["status"],
            store_scale=store["store_scale"],
            deposit_krw=store["deposit_krw"],
            interior_krw=store["interior_krw"],
            settled_through_day=store["settled_through_day"],
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
                    effective_from_day=d["effective_from_day"],
                    price_factor=d["price_factor"],
                    staff_count=d["staff_count"],
                    facility_score=d["facility_score"],
                )
                for d in store["decisions"]
            ),
        )

    # --- 결산 (8단계) ------------------------------------------------------

    async def list_settlements(self, user_id, epoch_id) -> tuple[SettlementRecord, ...]:
        mine = {s["id"] for s in self.stores.values() if s["user_id"] == user_id}
        return tuple(
            sorted(
                (s for s in self.settlements if s.store_id in mine),
                key=lambda s: (s.game_quarter, s.store_id),
            )
        )

    async def record_settlement(
        self, *, user_id, epoch_id, store_id, settlement, settled_through_day, game_day
    ) -> None:
        store = self.stores[store_id]
        if store["settled_through_day"] >= settled_through_day:
            return  # 멱등 — 같은 분기를 두 번 정산하지 않는다
        self.settlements.append(settlement)
        store["settled_through_day"] = settled_through_day
        if self._accounts is not None:
            wallet = self._accounts.wallets[user_id]
            applied = max(settlement.profit_krw, -wallet["cash_krw"])  # 지갑은 음수가 되지 않는다
            wallet["cash_krw"] += applied
            self._accounts.ledger.append(
                {"user_id": user_id, "source": "settlement", "amount_krw": applied}
            )
