from market.app.dtos.area_finance_dto import AreaFinanceQuery
from market.app.dtos.area_stats_dto import AreaHeader, ServiceRef
from market.app.use_cases.area_finance_interactor import AreaFinanceInteractor
from market.domain.value_objects.area_profile_vo import ServiceRank, StartupCost
from market.domain.value_objects.finance_vo import KeyMoneyBenchmark, RentBenchmark, Source


class _StubDetail:
    def __init__(self, header=True, rank=None, cost=None):
        self._header = AreaHeader(1001, "성수동카페거리", "성동구") if header else None
        self._rank = rank
        self._cost = cost

    async def find_header(self, trdar_code):
        return self._header

    async def resolve_service(self, trdar_code, service_code):
        return ServiceRef("CS100010", "커피-음료") if service_code == "CS100010" else None

    async def find_service_ranking(self, trdar_code, limit=12):
        return [self._rank] if self._rank else []

    async def find_startup_cost(self, industry_name):
        return self._cost


class _StubFinance:
    def __init__(self, rent=None, rate=(202608, 4.5), key_money=None):
        self.rent, self.rate = rent, rate
        self.key_money = key_money or {}
        self.key_money_calls: list[str] = []

    async def find_rent(self, trdar_code):
        return self.rent

    async def find_key_money(self, industry_group):
        self.key_money_calls.append(industry_group)
        return self.key_money.get(industry_group)

    async def find_loan_rate(self):
        return self.rate


RANK = ServiceRank(code="CS100010", name="커피-음료", monthly_sales=300_000_000, store_count=20,
                   sales_per_store=15_000_000, sales_qoq=None, closure_rate=None)
COST = StartupCost(industry_name="커피", year=2025, total_amount=80_000_000, brand_count=100)
RENT = RentBenchmark(year_quarter=20262, rent_per_sqm_krw=45_000, vacancy_rate=3.0, region_name="기타", level="zone")
Q = AreaFinanceQuery(trdar_code=1001, service_code="CS100010", equity=100_000_000)


async def test_상권_평균과_공정위_가정으로_빈_값을_채운다():
    view = await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    i = view.plan.inputs
    assert i.monthly_rent.value == 45_000 * 33 and i.monthly_rent.source == Source.AREA_AVG
    assert "기타 권역 평균" in i.monthly_rent.note and "33㎡" in i.monthly_rent.note
    assert i.startup_cost.value == 80_000_000 and i.startup_cost.source == Source.FRANCHISE
    assert i.deposit.value == i.monthly_rent.value * 10 and i.deposit.source == Source.ASSUMED
    # 인원 미입력 → 점주 본인 최저임금 1인분, 원가율에 카드 수수료 1.5% 가산(2026-09-17)
    assert i.monthly_payroll.value == 10_320 * 209 and "점주 본인" in i.monthly_payroll.note
    assert abs(i.cost_ratio.value - 0.315) < 1e-9 and "카드 결제 수수료 1.5%" in i.cost_ratio.note
    assert i.loan_rate.value == 4.5 and i.loan_rate.source == Source.ECOS
    assert view.plan.benchmark_margin == 0.087 and "공과금·소모품·배달 수수료 미반영" in view.assumption_note
    assert i.expected_monthly_sales.value == 15_000_000
    assert "손익분기" in view.headline and view.rent is RENT


async def test_임대료_레벨별로_라벨이_갈린다():
    area_rent = RentBenchmark(year_quarter=20262, rent_per_sqm_krw=45_000, vacancy_rate=3.0,
                               region_name="성수동카페거리", level="area")
    view = await AreaFinanceInteractor(_StubFinance(area_rent), _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    assert "성수동카페거리 상권 평균" in view.plan.inputs.monthly_rent.note

    city_rent = RentBenchmark(year_quarter=20262, rent_per_sqm_krw=45_000, vacancy_rate=3.0,
                               region_name="서울", level="city")
    view = await AreaFinanceInteractor(_StubFinance(city_rent), _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    assert "서울 전체 평균" in view.plan.inputs.monthly_rent.note


async def test_사용자_입력이_있으면_출처가_input이고_면적으로_월세를_환산하지_않는다():
    q = AreaFinanceQuery(trdar_code=1001, service_code="CS100010", equity=100_000_000,
                         monthly_rent=3_000_000, headcount=1, area_sqm=66.0, desired_loan=20_000_000,
                         sources={"equity": "history"}, equity_note="앞서 말씀하신 1억")
    view = await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=RANK, cost=COST)).calculate(q)
    i = view.plan.inputs
    assert i.monthly_rent.value == 3_000_000 and i.monthly_rent.source == Source.INPUT
    assert i.equity.source == Source.HISTORY and i.equity.note == "앞서 말씀하신 1억"
    assert i.monthly_payroll.value == 10_320 * 209 and i.desired_loan.value == 20_000_000


async def test_임대료가_없어도_월세를_말했으면_계산하고_둘_다_없으면_None():
    ok = await AreaFinanceInteractor(_StubFinance(None), _StubDetail(rank=RANK, cost=COST)).calculate(
        AreaFinanceQuery(1001, "CS100010", 100_000_000, monthly_rent=2_000_000))
    assert ok is not None and ok.rent is None
    none = await AreaFinanceInteractor(_StubFinance(None), _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    assert none is None


async def test_점포_5개_미만이면_매출을_넣지_않는다():
    small = ServiceRank(code="CS100010", name="커피-음료", monthly_sales=30_000_000, store_count=3,
                        sales_per_store=10_000_000, sales_qoq=None, closure_rate=None)
    view = await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=small, cost=COST)).calculate(Q)
    assert view.plan.inputs.expected_monthly_sales is None and view.plan.attainment is None


async def test_창업비용_없고_금리_없으면_가정치로_간다():
    view = await AreaFinanceInteractor(_StubFinance(RENT, rate=None), _StubDetail(rank=RANK, cost=None)).calculate(Q)
    i = view.plan.inputs
    assert i.startup_cost.value == 0 and i.startup_cost.source == Source.ASSUMED
    assert i.loan_rate.value == 4.5 and i.loan_rate.source == Source.ASSUMED


async def test_상권이나_업종이_없으면_None():
    assert await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(header=False)).calculate(Q) is None
    assert await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=RANK)).calculate(
        AreaFinanceQuery(1001, "CS999999", 100_000_000)) is None



FOOD_KM = KeyMoneyBenchmark(year=2025, industry_group="숙박 및 음식점업", key_money_ratio=79.1, median_krw=43_670_749)


async def test_권리금을_안_말하면_서울_업종군_중위수를_가정한다():
    finance = _StubFinance(RENT, key_money={"숙박 및 음식점업": FOOD_KM})
    view = await AreaFinanceInteractor(finance, _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    km = view.plan.inputs.key_money
    assert km.value == 43_670_749 and km.source == Source.ASSUMED
    assert km.note == "권리금 4,367만원 가정(R-ONE 2025 서울 숙박 및 음식점업 권리금 있는 점포 중위수, 있는 비율 79%)"
    assert finance.key_money_calls == ["숙박 및 음식점업"]  # 커피-음료(CS1) → 숙박·음식점업
    assert "권리금 4,367만원 가정" in view.assumption_note
    # 권리금이 CAPEX에 들어가 부족 자금이 커진다
    zero = await AreaFinanceInteractor(_StubFinance(RENT), _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    assert view.plan.capex == zero.plan.capex + 43_670_749


async def test_업종군_자료가_없으면_전체로_폴백하고_권리금을_말하면_입력이_이긴다():
    all_km = KeyMoneyBenchmark(year=2025, industry_group="전체", key_money_ratio=54.3, median_krw=38_153_274)
    finance = _StubFinance(RENT, key_money={"전체": all_km})
    view = await AreaFinanceInteractor(finance, _StubDetail(rank=RANK, cost=COST)).calculate(Q)
    assert finance.key_money_calls == ["숙박 및 음식점업", "전체"]
    assert view.plan.inputs.key_money.value == 38_153_274

    given = await AreaFinanceInteractor(_StubFinance(RENT, key_money={"전체": all_km}), _StubDetail(rank=RANK, cost=COST)).calculate(
        AreaFinanceQuery(1001, "CS100010", 100_000_000, key_money=0))
    assert given.plan.inputs.key_money.value == 0 and given.plan.inputs.key_money.source == Source.INPUT
