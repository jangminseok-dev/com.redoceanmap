from dataclasses import dataclass


@dataclass(frozen=True)
class OpenStoreCommand:

    user_id: int
    trdar_code: int
    service_code: str
    budget_krw: int  # 투입 자본 — 이 값이 규모와 시설을 함께 정한다
    staff_count: int
    price_factor: float


@dataclass(frozen=True)
class OpenStoreReceipt:

    store_id: int
    trdar_name: str
    service_name: str
    opened_game_day: int
    store_scale: float  # 상권 평균 점포 대비 규모
    facility_score: int  # 자본에서 역산한 시설 점수
    seat_count: int
    daily_capacity_customers: int  # 착석·포장 구성을 반영한 하루 수용
    takeout_ratio: float  # 이 업종에서 좌석을 쓰지 않는 손님 비율
    fitness: float
    deposit_krw: int  # 폐업 시 회수된다
    interior_krw: int  # 회수되지 않는다
    cash_delta_krw: int
    cash_krw: int
    assumed_monthly_rent_krw: int
