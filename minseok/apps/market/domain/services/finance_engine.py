"""창업 재무 엔진 — BEP·부족 자금·버틸 기간·금리 스트레스. LLM 없이 전부 결정론(FINANCE_ENGINE_2026-09-16 §4).

부족 자금은 이자 제외 고정비로 먼저 확정한다(이자 ↔ 대출액 순환 방지). 이자는 원리금 상환이 아니라
월 이자만 반영한다 — 가정으로 병기.
"""
from __future__ import annotations

from market.domain.services.cost_benchmarks import WORKING_CAPITAL_MONTHS
from market.domain.value_objects.finance_vo import FinanceInputs, FinancePlan, Scenario, StressPoint

STRESS_DELTAS_PP = (1.0, 2.0)
SCENARIO_FACTORS = (("pessimistic", 0.8), ("base", 1.0), ("optimistic", 1.2))


def _runway(cash_after: int, monthly_profit: int | None) -> float | None:
    if monthly_profit is None or monthly_profit >= 0:
        return None
    return round(cash_after / abs(monthly_profit), 1)


def plan(
    inputs: FinanceInputs, assumptions: tuple[str, ...] = (),
    benchmark_margin: float | None = None, benchmark_label: str = "",
) -> FinancePlan:
    cost_ratio = float(inputs.cost_ratio.value)
    if not 0.0 <= cost_ratio < 1.0:
        raise ValueError(f"cost_ratio는 0 이상 1 미만이어야 합니다: {cost_ratio}")
    contribution = 1.0 - cost_ratio

    equity = int(inputs.equity.value)
    capex = int(round(inputs.startup_cost.value + inputs.deposit.value + inputs.key_money.value))
    opex_base = int(round(inputs.monthly_rent.value + inputs.monthly_payroll.value))
    funding_gap = max(0, capex + opex_base * WORKING_CAPITAL_MONTHS - equity)
    loan = max(int(inputs.desired_loan.value), funding_gap)
    cash_after = max(0, equity + loan - capex)
    sales = int(inputs.expected_monthly_sales.value) if inputs.expected_monthly_sales else None

    def _at(rate: float) -> tuple[int, int, int, int | None]:
        interest = int(round(loan * rate / 100 / 12))
        fixed = opex_base + interest
        bep = int(round(fixed / contribution))
        profit = int(round(sales * contribution - fixed)) if sales is not None else None
        return interest, fixed, bep, profit

    base_rate = float(inputs.loan_rate.value)
    interest, fixed, bep, profit = _at(base_rate)
    attainment = round(sales / bep, 2) if sales is not None and bep > 0 else None

    stress = tuple(
        StressPoint(rate_delta_pp=d, loan_rate=round(base_rate + d, 2),
                    monthly_profit=_at(base_rate + d)[3],
                    runway_months=_runway(cash_after, _at(base_rate + d)[3]))
        for d in STRESS_DELTAS_PP
    )
    scenarios: tuple[Scenario, ...] = ()
    if sales is not None:
        scenarios = tuple(
            Scenario(
                key=key, sales_factor=f, monthly_sales=int(round(sales * f)),
                monthly_profit=int(round(sales * f * contribution - fixed)),
                runway_months=_runway(cash_after, int(round(sales * f * contribution - fixed))),
            )
            for key, f in SCENARIO_FACTORS
        )

    return FinancePlan(
        inputs=inputs, capex=capex, opex_base=opex_base, funding_gap=funding_gap, loan=loan,
        loan_interest=interest, fixed_monthly=fixed, bep_monthly_sales=bep, attainment=attainment,
        monthly_profit=profit, cash_after=cash_after, runway_months=_runway(cash_after, profit),
        stress=stress, scenarios=scenarios, assumptions=tuple(assumptions),
        benchmark_margin=benchmark_margin, benchmark_label=benchmark_label,
    )


def operating_margin(p: FinancePlan) -> float | None:
    """계산된 월 이익 ÷ 예상 월매출 — 매출이 없으면 None."""
    sales = p.inputs.expected_monthly_sales
    if p.monthly_profit is None or sales is None or sales.value <= 0:
        return None
    return p.monthly_profit / sales.value


def is_margin_overstated(p: FinancePlan, factor: float) -> bool:
    margin = operating_margin(p)
    return margin is not None and p.benchmark_margin is not None and margin > p.benchmark_margin * factor
