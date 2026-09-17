"""창업 재무 계산 계약 DTO — market 엔진 결과를 chat이 그대로 싣는 문장·수치.

문장(headline)은 market 도메인(finance_narrator)이 만든다 — AreaInsight와 같은 이유(소비자마다
임계값을 재구현하지 않는다). 금액은 원(int), 금리는 연 %.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AreaFinanceRequest:
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
    sources: dict[str, str] = field(default_factory=dict)  # 필드명 → input|history|profile
    equity_note: str = ""


@dataclass(frozen=True)
class FinanceInputItem:
    key: str
    value: float
    source: str
    note: str


@dataclass(frozen=True)
class AreaFinancePlanInfo:
    trdar_code: int
    trdar_name: str
    service_code: str
    service_name: str
    headline: str
    assumption_note: str
    inputs: tuple[FinanceInputItem, ...]
    capex: int
    funding_gap: int
    loan: int
    bep_monthly_sales: int
    attainment: float | None
    monthly_profit: int | None
    runway_months: float | None
    stress_runway: tuple[tuple[float, float | None], ...]  # (금리 +pp, runway)
    expected_monthly_sales: int | None
    rent_level: str | None  # area | zone | city
    vacancy_rate: float | None = None   # R-ONE 공실률(%) — 벤치마크가 없으면 None
    rent_region: str = ""                # 임대료 기준 지역명(예: 뚝섬)
    income_return: float | None = None   # R-ONE 상가 소득수익률(분기 %) — 임대료 기준 지역과 같은 단위
    capital_return: float | None = None  # 자본수익률(분기 %) — 자산가치 변동, 상권 과열·침체 신호
