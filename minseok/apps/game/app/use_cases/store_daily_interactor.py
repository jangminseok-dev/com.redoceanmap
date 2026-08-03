from __future__ import annotations

from game.app.dtos.store_daily_dto import (
    CustomerBucket,
    DailyRow,
    StoreDailyQuery,
    StoreDailyView,
    StoreSummary,
)
from game.app.dtos.store_dto import StoreRecord
from game.app.exceptions import StoreNotFound
from game.app.ports.input.store_daily_use_case import StoreDailyUseCase
from game.app.ports.output.game_clock_port import GameClockPort
from game.app.ports.output.game_store_repository import GameStoreRepository
from game.domain.clock.game_epoch import GAME_EPOCH_ID, SEASON_TICKS, describe
from game.domain.commerce import customer_sampler as customers
from game.domain.commerce import store_simulation as sim

MAX_DAYS = 90  # 한 분기치. 그 이상은 분기 결산(8단계)이 요약한다


class StoreDailyInteractor(StoreDailyUseCase):
    """가게 현황 대장.

    **일별 매출을 저장하지 않는다.** 창업 시각과 결정만 있으면 어느 날이든 재계산되므로
    (game-harness §1-A) 유저가 며칠 접속하지 않아도 가게는 장사한 것이 된다.
    """

    def __init__(self, stores: GameStoreRepository, clock: GameClockPort) -> None:
        self._stores = stores
        self._clock = clock

    async def list_stores(self, user_id: int) -> tuple[StoreSummary, ...]:
        moment = describe(self._clock.now_tick())
        records = await self._stores.list_stores(user_id, GAME_EPOCH_ID)
        summaries = []
        for record in records:
            last_day = self._last_active_day(record, moment.game_day)
            days = [
                sim.simulate_day(*self._context(record, day), day)
                for day in range(record.opened_game_day, last_day + 1)
            ]
            summaries.append(
                StoreSummary(
                    store_id=record.id,
                    trdar_name=record.trdar_name,
                    service_name=record.service_name,
                    status=record.status,
                    opened_game_day=record.opened_game_day,
                    days_open=max(0, last_day - record.opened_game_day + 1),
                    store_scale=round(record.store_scale, 4),
                    fitness=record.fitness,
                    cumulative_sales_krw=sum(d.simulated_sales_krw for d in days),
                    cumulative_profit_krw=sum(d.profit_krw for d in days),
                )
            )
        return tuple(summaries)

    async def get_daily(self, query: StoreDailyQuery) -> StoreDailyView:
        moment = describe(self._clock.now_tick())
        record = await self._stores.find_store(query.user_id, query.store_id, GAME_EPOCH_ID)
        if record is None:
            raise StoreNotFound("가게를 찾을 수 없습니다")

        last_day = self._last_active_day(record, moment.game_day)
        all_days = [
            sim.simulate_day(*self._context(record, day), day)
            for day in range(record.opened_game_day, last_day + 1)
        ]
        window = max(1, min(query.days, MAX_DAYS))
        recent = all_days[-window:]

        # 오늘 온 손님 표본 — 이 상권·업종의 실제 분포에서 뽑는다
        today_sample = customers.sample_customers(
            store_id=record.id,
            game_day=last_day,
            hour_share=record.area_hour_share,
            gender_share=record.area_gender_share,
            age_share=record.area_age_share,
        )
        setup, decision = self._context(record, last_day)

        return StoreDailyView(
            store_id=record.id,
            trdar_name=record.trdar_name,
            service_name=record.service_name,
            status=record.status,
            opened_game_day=record.opened_game_day,
            days_open=max(0, last_day - record.opened_game_day + 1),
            store_scale=round(record.store_scale, 4),
            fitness=record.fitness,
            seats=sim.seats(decision.facility_score),
            deposit_krw=record.deposit_krw,
            interior_krw=record.interior_krw,
            price_factor=decision.price_factor,
            staff_count=decision.staff_count,
            facility_score=decision.facility_score,
            observed_sales_per_store=record.observed_sales_per_store,
            observed_ticket_price=record.observed_ticket_price,
            assumed_monthly_rent_krw=sim.monthly_rent(setup),
            cumulative_sales_krw=sum(d.simulated_sales_krw for d in all_days),
            cumulative_profit_krw=sum(d.profit_krw for d in all_days),
            average_turned_away_ratio=round(
                sum(d.turned_away_ratio for d in all_days) / len(all_days), 4
            )
            if all_days
            else 0.0,
            rows=tuple(
                DailyRow(
                    game_day=d.game_day,
                    simulated_sales_krw=d.simulated_sales_krw,
                    simulated_customer_count=d.simulated_customer_count,
                    capacity_customer_count=d.capacity_customer_count,
                    turned_away_ratio=d.turned_away_ratio,
                    assumed_rent_krw=d.assumed_rent_krw,
                    assumed_labor_krw=d.assumed_labor_krw,
                    assumed_cogs_krw=d.assumed_cogs_krw,
                    assumed_utility_krw=d.assumed_utility_krw,
                    profit_krw=d.profit_krw,
                )
                for d in recent
            ),
            customers_by_age=self._bucket(today_sample, "age"),
            customers_by_hour=self._bucket(today_sample, "hour"),
            customers_by_taste=self._bucket(today_sample, "taste"),
            tick=moment.tick,
            game_day=moment.game_day,
            game_quarter=moment.game_quarter,
            season_over=moment.season_over,
        )

    @staticmethod
    def _bucket(sample, key: str) -> tuple[CustomerBucket, ...]:
        return tuple(
            CustomerBucket(label=label, count=count)
            for label, count in customers.summarize(sample, key)
        )

    @staticmethod
    def _last_active_day(record: StoreRecord, today: int) -> int:
        """시뮬레이션 마지막 날. 폐업했으면 그날까지, 시즌이 끝났으면 시즌 마지막 날까지."""
        season_last_day = (SEASON_TICKS - 1) // 60
        end = min(today, season_last_day)
        if record.closed_game_day is not None:
            end = min(end, record.closed_game_day)
        return max(record.opened_game_day, end)

    @staticmethod
    def _context(record: StoreRecord, game_day: int):
        """그날 유효한 결정을 찾아 시뮬레이션 입력을 만든다.

        결정을 바꾸면 그날부터 적용되고 과거는 그대로다 — 그래서 과거 재계산이 안정적이다.
        """
        applicable = [d for d in record.decisions if d.effective_from_day <= game_day]
        current = (
            max(applicable, key=lambda d: d.effective_from_day)
            if applicable
            else record.decisions[0]
        )
        setup = sim.StoreSetup(
            store_id=record.id,
            service_code=record.service_code,
            opened_game_day=record.opened_game_day,
            store_scale=record.store_scale,
            observed_sales_per_store=record.observed_sales_per_store,
            observed_ticket_price=record.observed_ticket_price,
            fitness=record.fitness,
            rent_location_factor=record.rent_location_factor,
            area_weekday_share=record.area_weekday_share,
        )
        decision = sim.StoreDecision(
            price_factor=current.price_factor,
            staff_count=current.staff_count,
            facility_score=current.facility_score,
        )
        return setup, decision
