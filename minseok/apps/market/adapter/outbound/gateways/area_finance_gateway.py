from __future__ import annotations

from dataclasses import fields

from hub.app.dtos.area_finance_dto import AreaFinancePlanInfo, AreaFinanceRequest, FinanceInputItem
from hub.app.ports.output.area_finance_port import AreaFinancePort
from market.app.dtos.area_finance_dto import AreaFinanceQuery
from market.app.ports.input.area_finance_use_case import AreaFinanceUseCase


class AreaFinanceGateway(AreaFinancePort):
    """허브 AreaFinancePort 구현 — area_finance 인터랙터에 위임하고 View를 계약 DTO로 옮긴다."""

    def __init__(self, use_case: AreaFinanceUseCase) -> None:
        self._use_case = use_case

    async def plan(self, request: AreaFinanceRequest) -> AreaFinancePlanInfo | None:
        view = await self._use_case.calculate(AreaFinanceQuery(
            trdar_code=request.trdar_code, service_code=request.service_code, equity=request.equity,
            deposit=request.deposit, monthly_rent=request.monthly_rent, key_money=request.key_money,
            startup_cost=request.startup_cost, area_sqm=request.area_sqm, headcount=request.headcount,
            desired_loan=request.desired_loan, sources=dict(request.sources), equity_note=request.equity_note,
        ))
        if view is None:
            return None
        p = view.plan
        return AreaFinancePlanInfo(
            trdar_code=view.trdar_code, trdar_name=view.trdar_name, service_code=view.service_code,
            service_name=view.service_name, headline=view.headline, assumption_note=view.assumption_note,
            inputs=tuple(
                FinanceInputItem(key=f.name, value=s.value, source=str(s.source), note=s.note)
                for f in fields(p.inputs) if (s := getattr(p.inputs, f.name)) is not None
            ),
            capex=p.capex, funding_gap=p.funding_gap, loan=p.loan, bep_monthly_sales=p.bep_monthly_sales,
            attainment=p.attainment, monthly_profit=p.monthly_profit, runway_months=p.runway_months,
            stress_runway=tuple((s.rate_delta_pp, s.runway_months) for s in p.stress),
            expected_monthly_sales=int(p.inputs.expected_monthly_sales.value) if p.inputs.expected_monthly_sales else None,
            rent_level=view.rent.level if view.rent else None,
        )
