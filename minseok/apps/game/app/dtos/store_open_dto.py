from dataclasses import dataclass


@dataclass(frozen=True)
class OpenStoreCommand:

    user_id: int
    trdar_code: int
    service_code: str
    budget_krw: int  # 투입 자본 — 이 값이 가게 규모를 정한다
    facility_score: int
    staff_count: int
    price_factor: float


@dataclass(frozen=True)
class OpenStoreReceipt:

    store_id: int
    trdar_name: str
    service_name: str
    opened_game_day: int
    store_scale: float  # 상권 평균 점포 대비 규모
    fitness: float
    deposit_krw: int  # 폐업 시 회수된다
    interior_krw: int  # 회수되지 않는다
    cash_delta_krw: int
    cash_krw: int
    assumed_monthly_rent_krw: int
