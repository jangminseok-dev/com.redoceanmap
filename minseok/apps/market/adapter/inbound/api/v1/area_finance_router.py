from dataclasses import fields

from fastapi import APIRouter, Depends, HTTPException, Query

from market.adapter.inbound.api.schemas.area_finance_schema import (
    AreaFinanceResponse, ScenarioSchema, SourcedValueSchema, StressSchema,
)
from market.app.dtos.area_finance_dto import AreaFinanceQuery
from market.app.ports.input.area_finance_use_case import AreaFinanceUseCase
from market.dependencies.area_finance_provider import get_area_finance_use_case

area_finance_router = APIRouter(prefix="/market", tags=["market"])
# `/myself`를 두지 않는다 — market 조회 슬라이스 라우터는 전부 prefix="/market"이라 cartographer의 자기소개 하나뿐.


@area_finance_router.get("/trdar/{trdar_code}/finance", response_model=AreaFinanceResponse)
async def get_area_finance(
    trdar_code: int,
    service_code: str = Query(description="업종 코드 (예: CS100010)"),
    equity: int = Query(ge=0, description="자기자본(원)"),
    deposit: int | None = Query(default=None, ge=0),
    monthly_rent: int | None = Query(default=None, ge=0),
    key_money: int | None = Query(default=None, ge=0),
    startup_cost: int | None = Query(default=None, ge=0),
    area_sqm: float | None = Query(default=None, gt=0),
    headcount: int | None = Query(default=None, ge=0),
    desired_loan: int | None = Query(default=None, ge=0),
    use_case: AreaFinanceUseCase = Depends(get_area_finance_use_case),
) -> AreaFinanceResponse:
    view = await use_case.calculate(AreaFinanceQuery(
        trdar_code=trdar_code, service_code=service_code, equity=equity, deposit=deposit,
        monthly_rent=monthly_rent, key_money=key_money, startup_cost=startup_cost, area_sqm=area_sqm,
        headcount=headcount, desired_loan=desired_loan,
    ))
    if view is None:
        raise HTTPException(status_code=404, detail=f"상권 {trdar_code} · 업종 {service_code}의 재무 계산 자료가 없습니다")
    p = view.plan
    return AreaFinanceResponse(
        trdarCode=view.trdar_code, trdarName=view.trdar_name, districtName=view.district_name,
        serviceCode=view.service_code, serviceName=view.service_name,
        headline=view.headline, assumptionNote=view.assumption_note,
        inputs=[
            SourcedValueSchema(key=f.name, value=s.value, source=str(s.source), note=s.note)
            for f in fields(p.inputs) if (s := getattr(p.inputs, f.name)) is not None
        ],
        capex=p.capex, fundingGap=p.funding_gap, loan=p.loan, fixedMonthly=p.fixed_monthly,
        bepMonthlySales=p.bep_monthly_sales, attainment=p.attainment, monthlyProfit=p.monthly_profit,
        cashAfter=p.cash_after, runwayMonths=p.runway_months,
        stress=[StressSchema(rateDeltaPp=s.rate_delta_pp, loanRate=s.loan_rate, monthlyProfit=s.monthly_profit,
                             runwayMonths=s.runway_months) for s in p.stress],
        scenarios=[ScenarioSchema(key=s.key, monthlySales=s.monthly_sales, monthlyProfit=s.monthly_profit,
                                  runwayMonths=s.runway_months) for s in p.scenarios],
        rentQuarter=view.rent.year_quarter if view.rent else None,
        rentLevel=view.rent.level if view.rent else None,
    )
