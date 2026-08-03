from __future__ import annotations

from dataclasses import replace

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

    async def _check_store_quota(self, user_id: int) -> None:
        """동시 운영 가게 수 제한. n+1호점은 **흑자 분기 결산 n회**가 쌓여야 열린다.

        "한 곳을 굴려 흑자를 내본 뒤에 늘린다"는 순서를 강제한다 — 자본만 있으면 첫날에
        세 곳을 여는 것을 막는다.
        """
        stores = await self._stores.list_stores(user_id, GAME_EPOCH_ID)
        open_count = sum(1 for s in stores if s.status == "open")
        if open_count >= rules.MAX_CONCURRENT_STORES:
            raise InvalidOrder(
                f"가게는 동시에 {rules.MAX_CONCURRENT_STORES}곳까지만 운영할 수 있습니다"
            )
        if open_count == 0:
            return  # 1호점은 조건 없다
        settlements = await self._stores.list_settlements(user_id, GAME_EPOCH_ID)
        profitable = sum(1 for s in settlements if s.profit_krw > 0)
        if profitable < open_count:
            raise InvalidOrder(
                f"{open_count + 1}호점은 흑자 분기 결산 {open_count}회가 필요합니다 "
                f"(현재 {profitable}회)"
            )

    async def open_store(self, command: OpenStoreCommand) -> OpenStoreReceipt:
        moment = describe(self._clock.now_tick())
        if moment.season_over:
            raise SeasonClosed("시즌이 종료되어 새로 창업할 수 없습니다")

        if not 0 <= command.staff_count <= MAX_STAFF:
            raise InvalidOrder(f"직원 수는 0~{MAX_STAFF}명이어야 합니다")
        if not MIN_PRICE_FACTOR <= command.price_factor <= MAX_PRICE_FACTOR:
            raise InvalidOrder(
                f"가격 계수는 {MIN_PRICE_FACTOR}~{MAX_PRICE_FACTOR} 범위여야 합니다"
            )
        if command.budget_krw <= 0:
            raise InvalidOrder("투입 자본은 1원 이상이어야 합니다")

        await self._check_store_quota(command.user_id)

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

        # 시설 점수는 유저가 넣지 않는다 — 투입 자본과 예상 수요에서 함께 역산한다.
        # 직접 입력이면 자본을 전부 보증금에 넣어 규모만 키운 "좌석 1석짜리 역세권 카페"가
        # 만들어진다(§4-1).
        scale, facility_score = sim.plan_opening(
            observed_sales_per_store=sales_per_store,
            observed_ticket_price=ticket_price,
            fitness=result.fitness,
            rent_location_factor=rent_location,
            service_code=command.service_code,
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
        takeout = rules.takeout_ratio(command.service_code).value
        deposit, interior = sim.opening_cost(setup, facility_score)
        total_cost = deposit + interior
        # 규모 → 비용 경로에 반올림이 두 번 끼어 예산을 원 단위로 넘길 수 있다. 그만큼 줄인다.
        if total_cost > budget and scale > rules.MIN_STORE_SCALE.value:
            scale = max(rules.MIN_STORE_SCALE.value, scale * budget / total_cost)
            setup = replace(setup, store_scale=scale)
            deposit, interior = sim.opening_cost(setup, facility_score)
            total_cost = deposit + interior
        # 규모는 최소치(MIN_STORE_SCALE) 아래로 못 내려가므로 자본이 그 최소 가게값에도
        # 못 미치면 비용이 투입 자본을 넘는다. **요청한 자본보다 많이 청구하지 않는다.**
        if total_cost > budget:
            raise InsufficientCash(
                f"이 상권에서 창업하려면 최소 {total_cost:,}원이 필요합니다 "
                f"(투입 가능 {budget:,}원)"
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
                "facility_score": facility_score,
            },
            cash_delta_krw=-total_cost,
        )

        return OpenStoreReceipt(
            store_id=store.id,
            trdar_name=profile.trdar_name,
            service_name=profile.service_name,
            opened_game_day=moment.game_day,
            store_scale=round(scale, 4),
            facility_score=facility_score,
            seat_count=sim.seats(facility_score),
            daily_capacity_customers=sim.daily_capacity_customers(facility_score, takeout),
            takeout_ratio=takeout,
            fitness=result.fitness,
            deposit_krw=deposit,
            interior_krw=interior,
            cash_delta_krw=-total_cost,
            cash_krw=account.cash_krw - total_cost,
            assumed_monthly_rent_krw=sim.monthly_rent(setup),
        )
