from __future__ import annotations

from market.app.dtos.area_finance_dto import AreaFinanceQuery, AreaFinanceView
from market.app.ports.input.area_finance_use_case import AreaFinanceUseCase
from market.app.ports.output.area_detail_repository import AreaDetailRepositoryPort
from market.app.ports.output.area_finance_repository import AreaFinanceRepositoryPort
from market.domain.services import cost_benchmarks as cb
from market.domain.services import finance_engine, finance_narrator
from market.domain.services.area_narrator import PAYBACK_MIN_STORES, franchise_industry_for
from market.domain.value_objects.finance_vo import FinanceInputs, Source, Sourced

_BUILDING_LABEL = "소규모 상가"
_LEVEL_LABEL = {
    "area": "{r} 상권 평균",
    "zone": "{r} 권역 평균(상권 단위 자료 없음)",
    "city": "서울 전체 평균(상권·권역 자료 없음)",
}


class AreaFinanceInteractor(AreaFinanceUseCase):
    """입력 → 폴백 순서(입력 > 상권 평균/공정위/한국은행 > 가정)로 FinanceInputs를 조립하고 엔진에 넘긴다.

    자기자본의 이력·프로파일 폴백은 chat이 채워서 넘긴다(sources 맵) — 여기서는 데이터 폴백만.
    """

    def __init__(self, finance: AreaFinanceRepositoryPort, detail: AreaDetailRepositoryPort) -> None:
        self._finance = finance
        self._detail = detail

    async def calculate(self, query: AreaFinanceQuery) -> AreaFinanceView | None:
        header = await self._detail.find_header(query.trdar_code)
        if header is None:
            return None
        service = await self._detail.resolve_service(query.trdar_code, query.service_code)
        if service is None:
            return None

        def given(field: str, value: float, note: str = "") -> Sourced:
            return Sourced(value, Source(query.sources.get(field, "input")), note)

        rent = await self._finance.find_rent(query.trdar_code)
        sqm = query.area_sqm or cb.DEFAULT_SHOP_SQM
        if query.monthly_rent is not None:
            monthly_rent = given("monthly_rent", query.monthly_rent)
        elif rent is not None:
            label = _LEVEL_LABEL.get(rent.level, "{r} 평균").format(r=rent.region_name)
            monthly_rent = Sourced(
                int(round(rent.rent_per_sqm_krw * sqm)), Source.AREA_AVG,
                f"{label} {_BUILDING_LABEL}, {sqm:.0f}㎡{' 가정' if query.area_sqm is None else ''}",
            )
        else:
            return None  # 임대료 미적재 + 월세 미입력 → chat이 되묻는다

        deposit = (given("deposit", query.deposit) if query.deposit is not None
                   else Sourced(monthly_rent.value * cb.DEPOSIT_MONTHS, Source.ASSUMED, f"보증금은 월세 {cb.DEPOSIT_MONTHS}개월분 가정"))
        key_money = (given("key_money", query.key_money) if query.key_money is not None
                     else Sourced(0, Source.ASSUMED, "권리금 0 가정"))

        if query.startup_cost is not None:
            startup_cost = given("startup_cost", query.startup_cost)
        else:
            industry = franchise_industry_for(service.name)
            cost = await self._detail.find_startup_cost(industry) if industry else None
            startup_cost = (Sourced(cost.total_amount, Source.FRANCHISE, f"공정위 {cost.industry_name}({cost.year}) 중앙값, 임대료·권리금 제외")
                            if cost else Sourced(0, Source.ASSUMED, "창업비용 자료 없음 — 0으로 가정"))

        payroll = (Sourced(cb.monthly_payroll(query.headcount), Source.ASSUMED, f"최저임금 기준 {query.headcount}명")
                   if query.headcount else Sourced(0, Source.ASSUMED, "1인 운영 가정"))
        bench = cb.benchmark_for(service.name)
        cost_ratio = Sourced(bench.cost_ratio, Source.ASSUMED, f"{bench.label} 원가율 {bench.cost_ratio:.0%}({bench.source})")
        rate = await self._finance.find_loan_rate()
        loan_rate = (Sourced(rate[1], Source.ECOS, f"한국은행 {rate[0] // 100}-{rate[0] % 100:02d} 대출평균")
                     if rate else Sourced(cb.DEFAULT_LOAN_RATE, Source.ASSUMED, f"금리 자료 없음 — {cb.DEFAULT_LOAN_RATE}% 가정"))
        desired_loan = (given("desired_loan", query.desired_loan) if query.desired_loan is not None
                        else Sourced(0, Source.ASSUMED))

        ranking = await self._detail.find_service_ranking(query.trdar_code, limit=60)
        rank = next((r for r in ranking if r.code == service.code), None)
        expected = None
        if rank and rank.sales_per_store and (rank.store_count or 0) >= PAYBACK_MIN_STORES:
            expected = Sourced(rank.sales_per_store, Source.AREA_AVG, f"{header.trdar_name} {service.name} 점포당 월매출")

        inputs = FinanceInputs(
            equity=given("equity", query.equity, query.equity_note), deposit=deposit, monthly_rent=monthly_rent,
            key_money=key_money, startup_cost=startup_cost, monthly_payroll=payroll, cost_ratio=cost_ratio,
            loan_rate=loan_rate, desired_loan=desired_loan, expected_monthly_sales=expected,
        )
        plan = finance_engine.plan(inputs, assumptions=(
            "이자만 반영(원리금 상환 제외)", f"운전자금 {cb.WORKING_CAPITAL_MONTHS}개월분 포함",
        ))
        return AreaFinanceView(
            trdar_code=header.trdar_code, trdar_name=header.trdar_name, district_name=header.district_name,
            service_code=service.code, service_name=service.name, plan=plan, rent=rent,
            headline=finance_narrator.headline(plan, header.trdar_name, service.name),
            assumption_note=finance_narrator.assumption_note(plan),
        )
