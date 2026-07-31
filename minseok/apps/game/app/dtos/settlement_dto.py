from dataclasses import dataclass


@dataclass(frozen=True)
class SettlementQuery:

    user_id: int


@dataclass(frozen=True)
class AdviceView:

    tone: str  # good | warn | bad
    message: str


@dataclass(frozen=True)
class SettlementView:
    """분기 결산 1건.

    `simulated_*`는 게임 규칙 + 결정론 난수, `assumed_*`는 게임 규칙 가정치다
    (game-harness §5-1). 매출 자체가 시뮬레이션 산출물이라 비용도 같은 결이다.
    """

    store_id: int
    trdar_name: str
    service_name: str
    game_quarter: int
    days_counted: int
    simulated_sales_krw: int
    assumed_rent_krw: int
    assumed_labor_krw: int
    assumed_cogs_krw: int
    assumed_utility_krw: int
    profit_krw: int
    customer_count: int
    average_turned_away_ratio: float
    performance_ratio: float  # 내 매출 ÷ 상권 평균 점포가 같은 규모였을 때의 매출
    advices: tuple[AdviceView, ...]


@dataclass(frozen=True)
class SettlementListView:

    settlements: tuple[SettlementView, ...]
    newly_settled: int  # 이번 호출에서 새로 확정된 분기 수
    total_profit_krw: int
    game_day: int
    game_quarter: int
    season_over: bool
