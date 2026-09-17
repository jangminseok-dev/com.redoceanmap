"""창업 재무 엔진 값객체 — 모든 입력값에 출처 태그를 붙여 답변이 "무엇을 가정했는지"를 병기한다."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Source(StrEnum):
    INPUT = "input"          # 사용자 발화
    HISTORY = "history"      # 이전 턴 승계
    PROFILE = "profile"      # user_profiles 예산 밴드
    AREA_AVG = "area_avg"    # R-ONE 상권/권역/서울 평균 · 상권 점포당 매출
    FRANCHISE = "franchise"  # 공정위 창업비용 중앙값
    ASSUMED = "assumed"      # 코드 가정치
    ECOS = "ecos"            # 한국은행 금리


@dataclass(frozen=True)
class Sourced:
    value: float
    source: Source
    note: str = ""  # "성수 상권 평균, 33㎡ 가정" 등 병기용


@dataclass(frozen=True)
class FinanceInputs:
    equity: Sourced                 # 자기자본(원)
    deposit: Sourced                # 보증금(원)
    monthly_rent: Sourced           # 월세(원)
    key_money: Sourced              # 권리금(원)
    startup_cost: Sourced           # 인테리어·설비·가맹(원) — 공정위 중앙값은 임대료·권리금 제외
    monthly_payroll: Sourced        # 인건비(원/월)
    cost_ratio: Sourced             # 변동비율(0~1)
    loan_rate: Sourced              # 연 %(예 4.53)
    desired_loan: Sourced           # 희망 대출(원)
    expected_monthly_sales: Sourced | None  # 점포당 월매출 — 소표본이면 None


@dataclass(frozen=True)
class StressPoint:
    rate_delta_pp: float
    loan_rate: float
    monthly_profit: int | None
    runway_months: float | None


@dataclass(frozen=True)
class Scenario:
    key: str            # pessimistic | base | optimistic
    sales_factor: float
    monthly_sales: int
    monthly_profit: int
    runway_months: float | None


@dataclass(frozen=True)
class FinancePlan:
    inputs: FinanceInputs
    capex: int
    opex_base: int          # 이자 제외 월 고정비
    funding_gap: int
    loan: int
    loan_interest: int      # 월 이자
    fixed_monthly: int      # 이자 포함 월 고정비
    bep_monthly_sales: int
    attainment: float | None      # 점포당 월매출 ÷ BEP
    monthly_profit: int | None
    cash_after: int               # 대출까지 받고 CAPEX를 치른 뒤 남는 현금
    runway_months: float | None   # 적자일 때만, 흑자면 None
    stress: tuple[StressPoint, ...]
    scenarios: tuple[Scenario, ...]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class RentBenchmark:
    year_quarter: int
    rent_per_sqm_krw: int
    vacancy_rate: float | None
    region_name: str
    level: str  # area | zone | city
    # R-ONE 임대동향 수익률(분기 %) — 소득(임대료) + 자본(자산가치 변동) = 투자. 2024Q3 이전 빈티지·미적재면 None
    income_return: float | None = None
    capital_return: float | None = None
    investment_return: float | None = None


@dataclass(frozen=True)
class KeyMoneyBenchmark:
    """R-ONE 서울 업종 대분류별 상가권리금(연간) — 수준은 **권리금 있는 점포** 기준."""

    year: int
    industry_group: str          # "숙박 및 음식점업" · "전체"
    key_money_ratio: float | None  # 권리금 있는 점포 비율(%)
    median_krw: int | None
