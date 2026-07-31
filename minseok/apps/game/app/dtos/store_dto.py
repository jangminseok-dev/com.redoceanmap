"""가게 상태 DTO — store_open과 store_daily 두 슬라이스가 함께 쓴다."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StoreDecisionRecord:
    effective_from_day: int
    price_factor: float
    staff_count: int
    facility_score: int


@dataclass(frozen=True)
class SettlementRecord:
    """영속된 분기 결산 1건."""

    store_id: int
    game_quarter: int
    days_counted: int
    total_sales_krw: int
    total_rent_krw: int
    total_labor_krw: int
    total_cogs_krw: int
    total_utility_krw: int
    profit_krw: int
    payload: dict


@dataclass(frozen=True)
class StoreRecord:
    """영속된 가게 1곳. `profile_snapshot`은 market 실데이터의 스냅샷이다."""

    id: int
    user_id: int
    trdar_code: int
    trdar_name: str
    service_code: str
    service_name: str
    opened_game_day: int
    closed_game_day: int | None
    status: str
    store_scale: float
    deposit_krw: int
    interior_krw: int
    settled_through_day: int  # 분기 결산 앵커 — 이 날까지는 정산이 끝났다
    # --- 스냅샷(실데이터) ---
    observed_sales_per_store: int
    observed_ticket_price: int
    fitness: float
    rent_location_factor: float
    area_weekday_share: tuple[float, ...]
    area_hour_share: tuple[float, ...]
    area_gender_share: tuple[float, ...]
    area_age_share: tuple[float, ...]
    decisions: tuple[StoreDecisionRecord, ...]
