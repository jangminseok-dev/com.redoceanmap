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


def seated_capacity(facility_score: int) -> int:
    """하루에 받을 수 있는 **착석** 손님 수 = 좌석 × 회전율."""
    return max(
        1,
        int(
            seats(facility_score)
            * rules.BASE_TURNOVER_PER_SEAT.value
            * turnover_factor(facility_score)
        ),
    )


def takeout_capacity(facility_score: int) -> int:
    """하루에 받을 수 있는 **포장** 손님 수.

    포장 손님은 자리를 차지하지 않으므로 좌석 수가 아니라 응대 처리량이 상한이다.
    같은 시설이 착석보다 훨씬 빠르게 돌아간다.
    """
    return max(
        1,
        int(
            seats(facility_score)
            * rules.TAKEOUT_TURNOVER_PER_SEAT.value
            * turnover_factor(facility_score)
        ),
    )


def daily_capacity_customers(facility_score: int, takeout_ratio: float) -> int:
    """그 업종 손님 구성에서 **아무도 돌려보내지 않고** 받을 수 있는 하루 손님 수.

    착석·포장 상한이 각각 따로 걸리므로 둘 중 먼저 차는 쪽이 총량을 정한다.
    구성비가 한쪽으로 쏠려 있으면 그쪽 상한만 의미가 있다.
    """
    seated_share = 1.0 - takeout_ratio
    limits = []
    if seated_share > 0:
        limits.append(seated_capacity(facility_score) / seated_share)
    if takeout_ratio > 0:
        limits.append(takeout_capacity(facility_score) / takeout_ratio)
    return max(1, int(min(limits)))


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


def interior_cost(facility_score: int, store_scale: float) -> int:
    """시설 점수를 세우는 비용. **회수되지 않는다** — 창업할 때도, 나중에 더 올릴 때도 같은 값이다."""
    return round(facility_score * rules.INTERIOR_COST_PER_POINT.value * store_scale)


def opening_cost(setup: StoreSetup, facility_score: int) -> tuple[int, int]:
    """(보증금, 인테리어). 보증금은 폐업 시 회수되고 인테리어는 회수되지 않는다."""
    deposit = round(monthly_rent(setup) * rules.DEPOSIT_MONTHS.value)
    return deposit, interior_cost(facility_score, setup.store_scale)


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


def facility_for_demand(demand_customers: float, takeout_ratio: float) -> int:
    """이만큼의 손님을 돌려보내지 않으려면 시설 점수가 얼마나 필요한가.

    수용력은 시설 점수에 대해 단조 증가하므로 이분 탐색으로 최솟값을 찾는다.
    """
    lo = int(rules.FACILITY_SCORE_MIN.value)
    hi = int(rules.FACILITY_SCORE_MAX.value)
    if daily_capacity_customers(hi, takeout_ratio) < demand_customers:
        return hi
    while lo < hi:
        mid = (lo + hi) // 2
        if daily_capacity_customers(mid, takeout_ratio) >= demand_customers:
            hi = mid
        else:
            lo = mid + 1
    return lo


def plan_opening(
    observed_sales_per_store: int,
    observed_ticket_price: int,
    fitness: float,
    rent_location_factor: float,
    service_code: str,
    budget_krw: int,
) -> tuple[float, int]:
    """투입 자본 하나로 **(규모, 시설 점수)를 함께** 정한다.

    시설을 유저가 직접 넣게 두면 "역세권인데 하루 2명"이 나온다 — 자본을 전부 보증금에
    밀어넣어 규모만 키우고 좌석은 1석인 가게가 만들어지기 때문이다. 그래서 **수요에서
    역산한다**: 그 규모가 부를 손님을 받을 만큼만 시설에 쓰고 나머지를 규모에 넣는다.

    시설을 키우면 규모에 쓸 몫이 줄고 → 수요가 줄고 → 필요한 시설도 준다. 한 번에 못 풀어서
    "필요 시설 ≤ 지금 시설"이 되는 최소 지점을 이분 탐색한다(순수 계산·결정론).
    """
    takeout = rules.takeout_ratio(service_code).value
    ticket = max(1, observed_ticket_price)

    def scale_at(facility: int) -> float:
        return scale_for_budget(
            observed_sales_per_store=observed_sales_per_store,
            rent_location_factor=rent_location_factor,
            facility_score=facility,
            budget_krw=budget_krw,
        )

    def shortfall(facility: int) -> int:
        """이 시설 점수로 정해진 규모의 수요가 요구하는 시설 - 지금 시설. 감소함수."""
        daily_sales = (
            observed_sales_per_store / rules.DAYS_PER_MONTH.value
            * scale_at(facility)
            * fitness
        )
        return facility_for_demand(daily_sales / ticket, takeout) - facility

    lo = int(rules.FACILITY_SCORE_MIN.value)
    hi = int(rules.FACILITY_SCORE_MAX.value)
    if shortfall(lo) <= 0:
        best = lo
    elif shortfall(hi) > 0:
        best = hi
    else:
        while lo < hi:
            mid = (lo + hi) // 2
            if shortfall(mid) <= 0:
                hi = mid
            else:
                lo = mid + 1
        best = lo
    return scale_at(best), best


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

    # 시설이 받을 수 있는 최대 — 여기서 "좋은 상권 + 작은 가게"가 손님을 돌려보낸다.
    # **착석과 포장은 상한이 따로다.** 포장 손님을 좌석에 묶으면 커피·제과처럼 포장이
    # 지배적인 업종이 구조적으로 매출을 못 낸다(§4-1).
    takeout_share = rules.takeout_ratio(setup.service_code).value
    seated_demand = demand_customers * (1.0 - takeout_share)
    takeout_demand = demand_customers * takeout_share
    served = int(
        min(seated_demand, seated_capacity(decision.facility_score))
        + min(takeout_demand, takeout_capacity(decision.facility_score))
    )
    capacity = daily_capacity_customers(decision.facility_score, takeout_share)
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
