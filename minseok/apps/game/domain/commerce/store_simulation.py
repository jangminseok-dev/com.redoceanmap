"""가게 일일 시뮬레이션 — 매출과 비용 (game-strategy §4-1 · §4-5).

순수 계산이다. 저장하지 않는다 — 창업 시각과 결정(decisions)만 있으면 어느 날이든 다시
계산된다(game-harness §1-A). 유저가 며칠 접속하지 않아도 가게는 장사한 것이 된다.

매출 상한이 **시설점수**로 정해지는 것이 이 시뮬레이션의 핵심이다. 좋은 상권에 작은 가게를
내면 손님을 돌려보낸다 — "상권은 좋은데 내 가게가 못 받는다"가 숫자로 보인다(아이러브커피 ①).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from game.domain.economy import rule_coefficients as rules
from game.domain.rng.deterministic import uniform


@dataclass(frozen=True)
class StoreSetup:
    """가게의 고정 조건 — 창업 시 결정되고 시즌 내내 유지된다."""

    store_id: int
    service_code: str
    opened_game_day: int
    store_scale: float  # 0.02~1.00 — 상권 평균 점포 대비 규모
    observed_sales_per_store: int  # 점포당 월매출(실데이터)
    observed_ticket_price: int  # 객단가(실데이터)
    fitness: float  # 0.4~1.6(적합도)
    rent_location_factor: float  # 0.6~1.6(유동인구 백분위)
    area_weekday_share: tuple[float, ...]  # 7 — 요일 리듬(실데이터)


@dataclass(frozen=True)
class StoreDecision:
    """유저가 바꿀 수 있는 것. 결정론 재계산의 입력이라 저장한다."""

    price_factor: float  # 0.6~1.3 — 가격을 올리면 객단가↑ 건수↓, 순효과가 이 계수
    staff_count: int
    facility_score: int


@dataclass(frozen=True)
class DailyResult:
    game_day: int
    simulated_sales_krw: int
    simulated_customer_count: int
    capacity_customer_count: int  # 받을 수 있었던 최대 손님 수
    turned_away_ratio: float  # 자리가 없어 돌아간 비율
    assumed_rent_krw: int
    assumed_labor_krw: int
    assumed_cogs_krw: int
    assumed_utility_krw: int
    profit_krw: int


def seats(facility_score: int) -> int:
    """시설점수 10점당 좌석 1석."""
    return max(1, int(facility_score * rules.SEATS_PER_FACILITY_POINT.value))


def turnover_factor(facility_score: int) -> float:
    """회전율 계수. 임계 점수에서 최대치에 닿고 그 위로는 좌석 수만 는다."""
    ratio = min(1.0, facility_score / rules.FACILITY_SCORE_FOR_MAX_TURNOVER.value)
    floor = rules.TURNOVER_MIN.value
    return floor + (1.0 - floor) * ratio


def daily_capacity_customers(facility_score: int) -> int:
    """하루에 받을 수 있는 최대 손님 수 = 좌석 × 회전율."""
    return max(
        1,
        int(
            seats(facility_score)
            * rules.BASE_TURNOVER_PER_SEAT.value
            * turnover_factor(facility_score)
        ),
    )


def awareness(days_open: int) -> float:
    """개업 후 인지도. 신규 창업 페널티이자 시간이 주는 보상이다."""
    if days_open < 0:
        return 0.0
    grown = 1.0 - math.exp(-days_open / rules.AWARENESS_TAU_DAYS.value)
    return max(rules.AWARENESS_FLOOR.value, grown)


def weekday_factor(setup: StoreSetup, game_day: int) -> float:
    """실데이터 요일 비중 ÷ 균등(1/7). 자료가 없으면 1.0."""
    shares = setup.area_weekday_share
    if len(shares) != 7 or sum(shares) <= 0:
        return 1.0
    return shares[game_day % 7] * 7.0


def monthly_rent(setup: StoreSetup) -> int:
    """월임대료 — 실데이터가 없어 매출에 비례시킨 **가정치**다."""
    return round(
        setup.observed_sales_per_store
        * rules.RENT_RATIO.value
        * setup.rent_location_factor
        * setup.store_scale
    )


def opening_cost(setup: StoreSetup, facility_score: int) -> tuple[int, int]:
    """(보증금, 인테리어). 보증금은 폐업 시 회수되고 인테리어는 회수되지 않는다."""
    deposit = round(monthly_rent(setup) * rules.DEPOSIT_MONTHS.value)
    interior = round(
        facility_score * rules.INTERIOR_COST_PER_POINT.value * setup.store_scale
    )
    return deposit, interior


def scale_for_budget(
    observed_sales_per_store: int,
    rent_location_factor: float,
    facility_score: int,
    budget_krw: int,
) -> float:
    """투입 자본으로 감당 가능한 규모.

    상권 평균 점포당 월매출은 수천만 원이라 초기 자본으로는 그 규모를 살 수 없다.
    "작게 시작해서 키운다"로 푼다 — 자본이 규모를 정하고 매출·비용이 함께 스케일된다.
    """
    full = StoreSetup(
        store_id=0,
        service_code="",
        opened_game_day=0,
        store_scale=1.0,
        observed_sales_per_store=observed_sales_per_store,
        observed_ticket_price=1,
        fitness=1.0,
        rent_location_factor=rent_location_factor,
        area_weekday_share=(),
    )
    deposit, interior = opening_cost(full, facility_score)
    total = deposit + interior
    if total <= 0:
        return rules.MAX_STORE_SCALE.value
    return max(
        rules.MIN_STORE_SCALE.value,
        min(rules.MAX_STORE_SCALE.value, budget_krw / total),
    )


def simulate_day(setup: StoreSetup, decision: StoreDecision, game_day: int) -> DailyResult:
    """하루치 매출과 비용. 같은 입력이면 언제 계산해도 같은 결과다."""
    days_open = game_day - setup.opened_game_day
    base_daily = (
        setup.observed_sales_per_store / rules.DAYS_PER_MONTH.value * setup.store_scale
    )
    noise_range = rules.DAILY_NOISE_RANGE.value
    noise = 1.0 + (uniform("store-day", f"{setup.store_id}|{game_day}") * 2 - 1) * noise_range

    demand_sales = (
        base_daily
        * awareness(days_open)
        * setup.fitness
        * decision.price_factor
        * weekday_factor(setup, game_day)
        * noise
    )

    ticket = max(1, round(setup.observed_ticket_price * decision.price_factor))
    demand_customers = max(0, round(demand_sales / ticket))

    # 시설이 받을 수 있는 최대 — 여기서 "좋은 상권 + 작은 가게"가 손님을 돌려보낸다
    capacity = daily_capacity_customers(decision.facility_score)
    served = min(demand_customers, capacity)
    turned_away = (
        (demand_customers - served) / demand_customers if demand_customers > 0 else 0.0
    )
    sales = served * ticket

    rent = round(monthly_rent(setup) / rules.DAYS_PER_MONTH.value)
    # 인건비도 규모에 비례한다 — 규모 16%짜리 매대에 정직원 월급을 물리면 어떤 입지를
    # 골라도 구조적으로 적자다(첫 밸런스 실측에서 확인). 작은 가게는 그만큼만 사람을 쓴다.
    labor = round(
        decision.staff_count
        * rules.BASE_WAGE_MONTHLY.value
        * setup.store_scale
        / rules.DAYS_PER_MONTH.value
    )
    cogs = round(sales * rules.cogs_ratio(setup.service_code).value)
    utility = round(
        sales * rules.UTILITY_SALES_RATIO.value
        + rules.UTILITY_FIXED_MONTHLY.value / rules.DAYS_PER_MONTH.value * setup.store_scale
    )

    return DailyResult(
        game_day=game_day,
        simulated_sales_krw=sales,
        simulated_customer_count=served,
        capacity_customer_count=capacity,
        turned_away_ratio=round(turned_away, 4),
        assumed_rent_krw=rent,
        assumed_labor_krw=labor,
        assumed_cogs_krw=cogs,
        assumed_utility_krw=utility,
        profit_krw=sales - rent - labor - cogs - utility,
    )
