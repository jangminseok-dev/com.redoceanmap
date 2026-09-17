"""재무 계산의 첫 줄 — 코드가 쓴다. LLM은 이 문장 뒤에 해석만 붙인다(FINANCE_ENGINE §5-4).

값마다 출처를 괄호로 병기해 사용자가 틀린 값을 한 마디로 고칠 수 있게 한다.
"""
from __future__ import annotations

from market.domain.services.cost_benchmarks import MARGIN_WARN_FACTOR
from market.domain.services.finance_engine import is_margin_overstated, operating_margin
from market.domain.value_objects.finance_vo import FinancePlan, Source, Sourced

_SOURCE_LABEL = {
    Source.INPUT: "입력", Source.HISTORY: "앞서 말씀하신 값", Source.PROFILE: "프로파일",
    Source.AREA_AVG: "상권 평균", Source.FRANCHISE: "공정위", Source.ASSUMED: "가정", Source.ECOS: "한국은행",
}


def won(amount: float) -> str:
    """1억 2,000만원 · 8,036만원 · 7만원 · 0원."""
    man = int(round(amount / 10_000))
    if man == 0:
        return "0원"
    if man >= 10_000:
        eok, rest = divmod(man, 10_000)
        return f"{eok}억원" if rest == 0 else f"{eok}억 {rest:,}만원"
    return f"{man:,}만원"


def _tag(s: Sourced) -> str:
    return s.note or _SOURCE_LABEL[s.source]


def input_line(plan: FinancePlan) -> str:
    i = plan.inputs
    parts = [
        f"자기자본 {won(i.equity.value)}({_tag(i.equity)})",
        f"월세 {won(i.monthly_rent.value)}({_tag(i.monthly_rent)})",
        f"창업비용 {won(i.startup_cost.value)}({_tag(i.startup_cost)})",
    ]
    if i.deposit.source != Source.ASSUMED:
        parts.append(f"보증금 {won(i.deposit.value)}({_tag(i.deposit)})")
    if i.monthly_payroll.value:
        parts.append(f"인건비 {won(i.monthly_payroll.value)}({_tag(i.monthly_payroll)})")
    return "·".join(parts)


def headline(plan: FinancePlan, trdar_name: str, service_name: str) -> str:
    out = [f"{input_line(plan)}으로 계산하면 손익분기 월매출은 {won(plan.bep_monthly_sales)}이에요."]
    sales = plan.inputs.expected_monthly_sales
    if sales is None or plan.attainment is None or plan.monthly_profit is None:
        out.append(f"{trdar_name} {service_name} 점포당 매출 표본이 적어 달성률·버틸 기간은 계산하지 않았어요.")
    else:
        out.append(
            f"{trdar_name} {service_name} 점포당 월매출 {won(sales.value)}이면 달성률 {plan.attainment:.0%}"
            f"(월 {'이익' if plan.monthly_profit >= 0 else '적자'} 약 {won(abs(plan.monthly_profit))})."
        )
        margin = operating_margin(plan)
        if is_margin_overstated(plan, MARGIN_WARN_FACTOR):
            # 공과금·소모품·배달 수수료 등 이 계산에 없는 비용 때문에 실제 이익은 대개 이보다 작다
            out.append(
                f"다만 이 계산의 영업이익률 {margin:.0%}는 {plan.benchmark_label} 업종 평균 {plan.benchmark_margin:.0%}보다"
                f" 크게 높아요 — 공과금·소모품·배달 수수료 같은 비용이 빠진 값이라, 업종 평균 이익률로 보면"
                f" 월 이익은 약 {won(sales.value * plan.benchmark_margin)}이에요."
            )
    out.append(f"가게를 열고 3개월 버티려면 부족 자금 {won(plan.funding_gap)}이 필요해요."
               if plan.funding_gap else "자기자본으로 개업 비용과 3개월 운전자금이 충당돼요.")
    if plan.runway_months is not None:
        out.append(f"적자가 이어지면 남은 현금으로 약 {plan.runway_months:.0f}개월 버틸 수 있어요.")
    if plan.stress and plan.monthly_profit is not None:
        parts = [
            f"{s.rate_delta_pp:g}%p 오르면 월 {'이익' if (s.monthly_profit or 0) >= 0 else '적자'} {won(abs(s.monthly_profit or 0))}"
            for s in plan.stress
        ]
        out.append("금리가 " + ", ".join(parts) + "이에요.")
    return " ".join(out)


def assumption_note(plan: FinancePlan) -> str:
    i = plan.inputs
    notes = [s.note for s in (i.deposit, i.key_money, i.startup_cost, i.monthly_payroll, i.cost_ratio, i.loan_rate)
             if s.source == Source.ASSUMED and s.note]
    notes.extend(plan.assumptions)
    return "가정: " + " · ".join(notes) if notes else ""
