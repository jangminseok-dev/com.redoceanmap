from __future__ import annotations

from game.app.dtos.settlement_dto import (
    AdviceView,
    SettlementListView,
    SettlementQuery,
    SettlementView,
)
from game.app.dtos.store_dto import SettlementRecord, StoreRecord
from game.app.ports.input.settlement_use_case import SettlementUseCase
from game.app.ports.output.game_clock_port import GameClockPort
from game.app.ports.output.game_store_repository import GameStoreRepository
from game.domain.clock.game_epoch import GAME_DAYS_PER_QUARTER, GAME_EPOCH_ID, describe
from game.domain.commerce import settlement as rules
from game.domain.commerce import store_simulation as sim
from game.domain.economy import rule_coefficients as coefficients


class SettlementInteractor(SettlementUseCase):
    """분기 결산 대장.

    **여기서 창업이 자산에 연결된다.** 일별 손익은 계산만 되다가 분기가 끝나야 지갑에
    반영된다 — 분기 결산은 캐시가 아니라 게임 규칙상 실재하는 사건이기 때문이다.

    누적 계산은 앵커(`settled_through_day`) 이후만 돈다. 그래서 시즌이 길어져도
    한 번에 도는 날짜는 최대 한 분기(90일)다.
    """

    def __init__(self, stores: GameStoreRepository, clock: GameClockPort) -> None:
        self._stores = stores
        self._clock = clock

    async def run_and_list(self, query: SettlementQuery) -> SettlementListView:
        moment = describe(self._clock.now_tick())
        season_last_day = rules.QUARTERS_PER_SEASON * GAME_DAYS_PER_QUARTER - 1
        today = min(moment.game_day, season_last_day)

        records = await self._stores.list_stores(query.user_id, GAME_EPOCH_ID)
        newly_settled = 0
        for store in records:
            windows = rules.pending_quarters(
                opened_game_day=store.opened_game_day,
                settled_through_day=store.settled_through_day,
                today=today,
                closed_game_day=store.closed_game_day,
            )
            for window in windows:
                await self._stores.record_settlement(
                    user_id=query.user_id,
                    epoch_id=GAME_EPOCH_ID,
                    store_id=store.id,
                    settlement=self._settle(store, window),
                    settled_through_day=window.end_day,
                    game_day=window.end_day,
                )
                newly_settled += 1

        stored = await self._stores.list_settlements(query.user_id, GAME_EPOCH_ID)
        by_store = {s.id: s for s in records}
        views = tuple(
            self._to_view(record, by_store.get(record.store_id)) for record in stored
        )
        return SettlementListView(
            settlements=views,
            newly_settled=newly_settled,
            total_profit_krw=sum(v.profit_krw for v in views),
            game_day=moment.game_day,
            game_quarter=moment.game_quarter,
            season_over=moment.season_over,
        )

    @staticmethod
    def _settle(store: StoreRecord, window: rules.QuarterWindow) -> SettlementRecord:
        """한 분기를 재계산해 합산한다. 일별 매출을 저장하지 않으므로 결산도 재계산이다."""
        setup = sim.StoreSetup(
            store_id=store.id,
            service_code=store.service_code,
            opened_game_day=store.opened_game_day,
            store_scale=store.store_scale,
            observed_sales_per_store=store.observed_sales_per_store,
            observed_ticket_price=store.observed_ticket_price,
            fitness=store.fitness,
            rent_location_factor=store.rent_location_factor,
            area_weekday_share=store.area_weekday_share,
        )
        days = []
        for game_day in range(window.start_day, window.end_day + 1):
            applicable = [d for d in store.decisions if d.effective_from_day <= game_day]
            current = (
                max(applicable, key=lambda d: d.effective_from_day)
                if applicable
                else store.decisions[0]
            )
            days.append(
                sim.simulate_day(
                    setup,
                    sim.StoreDecision(
                        price_factor=current.price_factor,
                        staff_count=current.staff_count,
                        facility_score=current.facility_score,
                    ),
                    game_day,
                )
            )

        sales = sum(d.simulated_sales_krw for d in days)
        rent = sum(d.assumed_rent_krw for d in days)
        labor = sum(d.assumed_labor_krw for d in days)
        cogs = sum(d.assumed_cogs_krw for d in days)
        utility = sum(d.assumed_utility_krw for d in days)
        profit = sum(d.profit_krw for d in days)
        turned_away = sum(d.turned_away_ratio for d in days) / len(days) if days else 0.0

        # 상권 평균 점포가 같은 규모였다면 얼마를 팔았을까 — 그 대비 성과
        baseline = (
            store.observed_sales_per_store
            / coefficients.DAYS_PER_MONTH.value
            * store.store_scale
            * len(days)
        )
        performance = sales / baseline if baseline > 0 else 0.0

        advices = rules.advise(
            profit_krw=profit,
            average_turned_away_ratio=turned_away,
            performance_ratio=performance,
            fitness=store.fitness,
        )
        return SettlementRecord(
            store_id=store.id,
            game_quarter=window.game_quarter,
            days_counted=window.days,
            total_sales_krw=sales,
            total_rent_krw=rent,
            total_labor_krw=labor,
            total_cogs_krw=cogs,
            total_utility_krw=utility,
            profit_krw=profit,
            payload={
                "customer_count": sum(d.simulated_customer_count for d in days),
                "average_turned_away_ratio": round(turned_away, 4),
                "performance_ratio": round(performance, 4),
                "advices": [{"tone": a.tone, "message": a.message} for a in advices],
            },
        )

    @staticmethod
    def _to_view(record: SettlementRecord, store: StoreRecord | None) -> SettlementView:
        payload = record.payload or {}
        return SettlementView(
            store_id=record.store_id,
            trdar_name=store.trdar_name if store else "",
            service_name=store.service_name if store else "",
            game_quarter=record.game_quarter,
            days_counted=record.days_counted,
            simulated_sales_krw=record.total_sales_krw,
            assumed_rent_krw=record.total_rent_krw,
            assumed_labor_krw=record.total_labor_krw,
            assumed_cogs_krw=record.total_cogs_krw,
            assumed_utility_krw=record.total_utility_krw,
            profit_krw=record.profit_krw,
            customer_count=int(payload.get("customer_count", 0)),
            average_turned_away_ratio=float(payload.get("average_turned_away_ratio", 0.0)),
            performance_ratio=float(payload.get("performance_ratio", 0.0)),
            advices=tuple(
                AdviceView(tone=a.get("tone", "warn"), message=a.get("message", ""))
                for a in payload.get("advices", [])
            ),
        )
