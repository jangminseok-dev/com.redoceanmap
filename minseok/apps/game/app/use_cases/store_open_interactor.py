from __future__ import annotations

from game.app.dtos.store_open_dto import OpenStoreCommand, OpenStoreReceipt
from game.app.exceptions import (
    AreaProfileUnavailable,
    InsufficientCash,
    InvalidOrder,
    SeasonClosed,
)
from game.app.ports.input.store_open_use_case import StoreOpenUseCase
from game.app.ports.output.game_account_repository import GameAccountRepository
from game.app.ports.output.game_clock_port import GameClockPort
from game.app.ports.output.game_store_repository import GameStoreRepository
from game.domain.clock.game_epoch import DATA_QUARTER, GAME_EPOCH_ID, RULES_VERSION, describe
from game.domain.commerce import fitness as fitness_rules
from game.domain.commerce import store_simulation as sim
from game.domain.economy import rule_coefficients as rules
from game.domain.trading.trading_rules import INITIAL_CASH_KRW, investable_cash
from hub.app.ports.output.area_demand_profile_port import AreaDemandProfilePort

MIN_FACILITY_SCORE = 10
MAX_FACILITY_SCORE = 2_000
MAX_STAFF = 20
MIN_PRICE_FACTOR = 0.6
MAX_PRICE_FACTOR = 1.3


class StoreOpenInteractor(StoreOpenUseCase):
    """창업 대장.

    투입 자본이 **가게 규모를 정한다.** 상권 평균 점포당 월매출은 수천만 원이라 초기 자본으로
    그 규모를 살 수 없다 — "작게 시작해서 키운다"로 푼다(game-strategy §4-5).
    """

    def __init__(
        self,
        profiles: AreaDemandProfilePort,
        stores: GameStoreRepository,
        accounts: GameAccountRepository,
        clock: GameClockPort,
    ) -> None:
        self._profiles = profiles
        self._stores = stores
        self._accounts = accounts
        self._clock = clock

    async def open_store(self, command: OpenStoreCommand) -> OpenStoreReceipt:
        moment = describe(self._clock.now_tick())
        if moment.season_over:
            raise SeasonClosed("시즌이 종료되어 새로 창업할 수 없습니다")

        if not MIN_FACILITY_SCORE <= command.facility_score <= MAX_FACILITY_SCORE:
            raise InvalidOrder(
                f"시설 점수는 {MIN_FACILITY_SCORE}~{MAX_FACILITY_SCORE} 범위여야 합니다"
            )
        if not 0 <= command.staff_count <= MAX_STAFF:
            raise InvalidOrder(f"직원 수는 0~{MAX_STAFF}명이어야 합니다")
        if not MIN_PRICE_FACTOR <= command.price_factor <= MAX_PRICE_FACTOR:
            raise InvalidOrder(
                f"가격 계수는 {MIN_PRICE_FACTOR}~{MAX_PRICE_FACTOR} 범위여야 합니다"
            )
        if command.budget_krw <= 0:
            raise InvalidOrder("투입 자본은 1원 이상이어야 합니다")

        profile = await self._profiles.get_demand_profile(
            trdar_code=command.trdar_code,
            service_code=command.service_code,
            year_quarter=DATA_QUARTER,
        )
        if profile is None:
            raise AreaProfileUnavailable(
                f"상권 {command.trdar_code} · 업종 {command.service_code}의 자료가 없습니다"
            )

        account = await self._accounts.load(command.user_id, GAME_EPOCH_ID)
        if account is None:
            account = await self._accounts.create(
                user_id=command.user_id,
                epoch_id=GAME_EPOCH_ID,
                rule_version=RULES_VERSION,
                initial_cash_krw=INITIAL_CASH_KRW,
                game_day=moment.game_day,
            )
        budget = min(command.budget_krw, investable_cash(account.cash_krw))
        if budget <= 0:
            raise InsufficientCash("투자 가능 금액이 없습니다 (최소 생활자금은 쓸 수 없습니다)")

        sales_per_store = profile.observed_monthly_sales_amount // max(
            profile.observed_store_count, 1
        )
        ticket_price = profile.observed_monthly_sales_amount // max(
            profile.observed_monthly_sales_count, 1
        )
        if sales_per_store <= 0:
            raise AreaProfileUnavailable(
                "이 상권·업종은 매출 기록이 없어 창업 기준을 세울 수 없습니다"
            )

        result = fitness_rules.evaluate(
            industry_age_share=profile.industry_age_share,
            industry_gender_share=profile.industry_gender_share,
            industry_hour_share=profile.industry_hour_share,
            floating_age_share=profile.floating_age_share,
            floating_gender_share=profile.floating_gender_share,
            floating_hour_share=profile.floating_hour_share,
            saturation_percentile=profile.saturation_percentile,
            closure_rate_percentile=profile.closure_rate_percentile,
            operating_months_percentile=profile.operating_months_percentile,
        )
        # 임대료 입지계수 — 유동인구가 많은 상권일수록 비싸다(가정치)
        rent_location = rules.RENT_LOCATION_MIN.value + (
            rules.RENT_LOCATION_MAX.value - rules.RENT_LOCATION_MIN.value
        ) * min(1.0, profile.saturation_percentile)

        scale = sim.scale_for_budget(
            observed_sales_per_store=sales_per_store,
            rent_location_factor=rent_location,
            facility_score=command.facility_score,
            budget_krw=budget,
        )
        setup = sim.StoreSetup(
            store_id=0,
            service_code=command.service_code,
            opened_game_day=moment.game_day,
            store_scale=scale,
            observed_sales_per_store=sales_per_store,
            observed_ticket_price=ticket_price,
            fitness=result.fitness,
            rent_location_factor=rent_location,
            area_weekday_share=profile.area_weekday_share,
        )
        deposit, interior = sim.opening_cost(setup, command.facility_score)
        total_cost = deposit + interior
        if total_cost > investable_cash(account.cash_krw):
            raise InsufficientCash(
                f"창업 비용을 낼 수 없습니다 (필요 {total_cost:,}원 · "
                f"가능 {investable_cash(account.cash_krw):,}원)"
            )

        store = await self._stores.create_store(
            user_id=command.user_id,
            epoch_id=GAME_EPOCH_ID,
            trdar_code=profile.trdar_code,
            service_code=profile.service_code,
            opened_game_day=moment.game_day,
            store_scale=scale,
            deposit_krw=deposit,
            interior_krw=interior,
            profile_snapshot={
                "trdar_name": profile.trdar_name,
                "service_name": profile.service_name,
                "observed_sales_per_store": sales_per_store,
                "observed_ticket_price": ticket_price,
                "fitness": result.fitness,
                "rent_location_factor": rent_location,
                "area_weekday_share": list(profile.area_weekday_share),
                "area_hour_share": list(profile.area_hour_share),
                "area_gender_share": list(profile.area_gender_share),
                "area_age_share": list(profile.area_age_share),
            },
            decision={
                "price_factor": command.price_factor,
                "staff_count": command.staff_count,
                "facility_score": command.facility_score,
            },
            cash_delta_krw=-total_cost,
        )

        return OpenStoreReceipt(
            store_id=store.id,
            trdar_name=profile.trdar_name,
            service_name=profile.service_name,
            opened_game_day=moment.game_day,
            store_scale=round(scale, 4),
            fitness=result.fitness,
            deposit_krw=deposit,
            interior_krw=interior,
            cash_delta_krw=-total_cost,
            cash_krw=account.cash_krw - total_cost,
            assumed_monthly_rent_krw=sim.monthly_rent(setup),
        )
