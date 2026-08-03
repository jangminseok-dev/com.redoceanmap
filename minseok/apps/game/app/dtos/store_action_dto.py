"""가게 운영 액션 DTO — 창업 후에 유저가 내리는 결정들.

창업(store_open)과 분리한 이유: 창업은 자본에서 규모를 역산하는 1회성 계산이고,
운영은 이미 선 가게의 파라미터를 바꾸는 것이다. 저장 대상도 다르다(가게 행 vs 결정 이력).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class StoreDecisionCommand:
    """가격·직원·시설 변경. 지정하지 않은 항목은 직전 결정을 그대로 잇는다."""

    user_id: int
    store_id: int
    price_factor: float | None = None
    staff_count: int | None = None
    facility_score: int | None = None  # 증가만 허용 — 인테리어는 되팔 수 없다


@dataclass(frozen=True)
class StoreDecisionReceipt:
    store_id: int
    effective_from_day: int  # 오늘 다음 날 — 확정된 과거는 바뀌지 않는다
    price_factor: float
    staff_count: int
    facility_score: int
    facility_added: int
    interior_cost_krw: int  # 시설 추가투자분(회수 불가)
    cash_delta_krw: int
    cash_krw: int


@dataclass(frozen=True)
class CloseStoreCommand:
    user_id: int
    store_id: int


@dataclass(frozen=True)
class CloseStoreReceipt:
    store_id: int
    closed_game_day: int
    deposit_refund_krw: int   # 보증금은 돌려받는다
    interior_lost_krw: int    # 인테리어는 회수되지 않는다
    cash_delta_krw: int
    cash_krw: int
    # 폐업일이 낀 분기의 손익은 여기서 정산하지 않는다 — 결산 조회 때 확정된다
    # (지연 실행, game-harness §2). `pending_quarters`가 폐업 시 부분 구간을 만든다.
    pending_settlement: bool
