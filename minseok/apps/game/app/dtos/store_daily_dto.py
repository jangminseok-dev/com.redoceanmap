from dataclasses import dataclass


@dataclass(frozen=True)
class StoreDailyQuery:

    user_id: int
    store_id: int
    days: int  # 최근 며칠을 보여줄지


@dataclass(frozen=True)
class DailyRow:

    game_day: int
    simulated_sales_krw: int
    simulated_customer_count: int
    capacity_customer_count: int
    turned_away_ratio: float
    assumed_rent_krw: int
    assumed_labor_krw: int
    assumed_cogs_krw: int
    assumed_utility_krw: int
    profit_krw: int


@dataclass(frozen=True)
class CustomerBucket:

    label: str
    count: int


@dataclass(frozen=True)
class StoreSummary:
    """가게 목록용 한 줄."""

    store_id: int
    trdar_name: str
    service_name: str
    status: str
    opened_game_day: int
    days_open: int
    store_scale: float
    fitness: float
    cumulative_sales_krw: int
    cumulative_profit_krw: int


@dataclass(frozen=True)
class StoreDailyView:
    """가게 현황 — 누적 손익과 최근 일별 내역, 그리고 오늘 온 손님.

    `observed_*`는 실데이터, `assumed_*`는 게임 규칙, `simulated_*`는 규칙+결정론 난수다
    (game-harness §5-1).
    """

    store_id: int
    trdar_name: str
    service_name: str
    status: str
    opened_game_day: int
    days_open: int
    store_scale: float
    fitness: float
    seats: int
    deposit_krw: int
    interior_krw: int

    # 지금 유효한 운영 결정 — 화면이 조정 폼의 기본값으로 쓴다(하드코딩 금지)
    price_factor: float
    staff_count: int
    facility_score: int

    observed_sales_per_store: int
    observed_ticket_price: int
    assumed_monthly_rent_krw: int

    cumulative_sales_krw: int
    cumulative_profit_krw: int
    average_turned_away_ratio: float

    rows: tuple[DailyRow, ...]
    customers_by_age: tuple[CustomerBucket, ...]
    customers_by_hour: tuple[CustomerBucket, ...]
    customers_by_taste: tuple[CustomerBucket, ...]

    tick: int
    game_day: int
    game_quarter: int
    season_over: bool
