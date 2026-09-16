from __future__ import annotations

from dataclasses import dataclass, field

from market.domain.value_objects.finance_vo import FinancePlan, RentBenchmark


@dataclass(frozen=True)
class AreaFinanceQuery:
    """재무 계산 입력. None은 '사용자가 말하지 않음' — 인터랙터가 상권 평균·공정위·가정으로 채운다.

    sources: 값을 준 쪽이 chat일 때 출처(input|history|profile)를 필드명별로 알려 준다. 없으면 input.
    """

    trdar_code: int
    service_code: str
    equity: int
    deposit: int | None = None
    monthly_rent: int | None = None
    key_money: int | None = None
    startup_cost: int | None = None
    area_sqm: float | None = None
    headcount: int | None = None
    desired_loan: int | None = None
    sources: dict[str, str] = field(default_factory=dict)
    equity_note: str = ""


@dataclass(frozen=True)
class AreaFinanceView:
    trdar_code: int
    trdar_name: str
    district_name: str
    service_code: str
    service_name: str
    plan: FinancePlan
    rent: RentBenchmark | None
    headline: str
    assumption_note: str
