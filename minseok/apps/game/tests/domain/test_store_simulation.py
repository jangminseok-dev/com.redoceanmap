import pytest

from game.domain.commerce.store_simulation import (
    StoreDecision,
    StoreSetup,
    awareness,
    daily_capacity_customers,
    monthly_rent,
    opening_cost,
    scale_for_budget,
    seats,
    simulate_day,
    turnover_factor,
)
from game.domain.economy import rule_coefficients as rules

SALES_PER_STORE = 30_000_000
TICKET = 5_000
WEEKDAY = (0.15, 0.14, 0.14, 0.15, 0.16, 0.14, 0.12)


def _setup(fitness: float = 1.0, scale: float = 0.16) -> StoreSetup:
    return StoreSetup(
        store_id=1,
        service_code="CS100010",
        opened_game_day=0,
        store_scale=scale,
        observed_sales_per_store=SALES_PER_STORE,
        observed_ticket_price=TICKET,
        fitness=fitness,
        rent_location_factor=1.0,
        area_weekday_share=WEEKDAY,
    )


def _quarter_profit(fitness: float, facility: int = 300, budget: int = 3_000_000) -> int:
    scale = scale_for_budget(SALES_PER_STORE, 1.0, facility, budget)
    setup = _setup(fitness=fitness, scale=scale)
    decision = StoreDecision(price_factor=1.0, staff_count=2, facility_score=facility)
    return sum(simulate_day(setup, decision, d).profit_krw for d in range(90))


# --- 시설 (아이러브커피 ① 이식) ---------------------------------------------

def test_시설점수_10점당_좌석_1석이다():
    assert seats(100) == 10
    assert seats(850) == 85


def test_회전율은_임계점수에서_최대에_닿는다():
    assert turnover_factor(0) == pytest.approx(rules.TURNOVER_MIN.value)
    assert turnover_factor(850) == pytest.approx(1.0)
    assert turnover_factor(2000) == pytest.approx(1.0)  # 그 위로는 좌석만 는다


def test_수용력은_시설에_비례한다():
    assert daily_capacity_customers(300) > daily_capacity_customers(100)


def test_좋은_상권에_작은_가게를_내면_손님을_돌려보낸다():
    """"상권은 좋은데 내 가게가 못 받는다"가 숫자로 보여야 한다."""
    setup = _setup(fitness=1.6, scale=0.5)
    small = simulate_day(setup, StoreDecision(1.0, 1, 50), 60)
    large = simulate_day(setup, StoreDecision(1.0, 1, 800), 60)
    assert small.turned_away_ratio > 0.5
    assert large.turned_away_ratio < small.turned_away_ratio
    assert large.simulated_sales_krw > small.simulated_sales_krw


# --- 인지도 -----------------------------------------------------------------

def test_인지도는_개업_직후_낮고_시간이_지나면_오른다():
    assert awareness(0) == pytest.approx(rules.AWARENESS_FLOOR.value)
    assert awareness(30) > awareness(3)
    assert awareness(200) < 1.0


# --- 규모 -------------------------------------------------------------------

def test_투입_자본이_규모를_정한다():
    small = scale_for_budget(SALES_PER_STORE, 1.0, 100, 1_000_000)
    big = scale_for_budget(SALES_PER_STORE, 1.0, 100, 10_000_000)
    assert small < big
    assert rules.MIN_STORE_SCALE.value <= small <= rules.MAX_STORE_SCALE.value
    assert big <= rules.MAX_STORE_SCALE.value  # 상권 평균을 넘지 않는다


def test_보증금은_임대료에_비례하고_인테리어는_시설에_비례한다():
    setup = _setup()
    deposit, interior = opening_cost(setup, 300)
    assert deposit == round(monthly_rent(setup) * rules.DEPOSIT_MONTHS.value)
    assert interior > opening_cost(setup, 100)[1]


# --- 밸런스 (game-strategy §4-6: 절반은 적자) --------------------------------

def test_적합도가_흑자와_적자를_가른다():
    """이 게임의 핵심 메시지 — 이상한 곳에 이상한 업종으로 창업하면 망한다."""
    assert _quarter_profit(1.5) > 0
    assert _quarter_profit(1.2) > 0
    assert _quarter_profit(0.79) < 0
    assert _quarter_profit(0.5) < 0


def test_적합도가_높을수록_순익이_크다():
    profits = [_quarter_profit(f) for f in (0.5, 0.79, 1.0, 1.2, 1.5)]
    assert profits == sorted(profits)


# --- 결정론 -----------------------------------------------------------------

def test_같은_날을_두_번_계산해도_같다():
    setup, decision = _setup(), StoreDecision(1.0, 2, 300)
    assert simulate_day(setup, decision, 42) == simulate_day(setup, decision, 42)


def test_계산_순서가_결과를_바꾸지_않는다():
    setup, decision = _setup(), StoreDecision(1.0, 2, 300)
    ascending = [simulate_day(setup, decision, d).simulated_sales_krw for d in range(10, 20)]
    descending = [simulate_day(setup, decision, d).simulated_sales_krw for d in range(19, 9, -1)]
    assert ascending == descending[::-1]


def test_요일_리듬이_매출에_반영된다():
    setup, decision = _setup(), StoreDecision(1.0, 2, 2000)  # 수용력을 키워 cap 영향 제거
    sales = [simulate_day(setup, decision, d).simulated_sales_krw for d in range(70, 77)]
    assert len(set(sales)) > 1  # 요일마다 다르다


def test_금액은_전부_정수다():
    result = simulate_day(_setup(), StoreDecision(1.0, 2, 300), 30)
    for value in (
        result.simulated_sales_krw,
        result.assumed_rent_krw,
        result.assumed_labor_krw,
        result.assumed_cogs_krw,
        result.assumed_utility_krw,
        result.profit_krw,
    ):
        assert isinstance(value, int)
