from hub.app.dtos.area_finance_dto import AreaFinanceRequest
from market.adapter.outbound.gateways.area_finance_gateway import AreaFinanceGateway
from market.app.dtos.area_finance_dto import AreaFinanceView
from market.domain.services import finance_engine as fe
from market.domain.value_objects.finance_vo import FinanceInputs, RentBenchmark, Source, Sourced


def _view() -> AreaFinanceView:
    plan = fe.plan(FinanceInputs(
        equity=Sourced(100_000_000, Source.INPUT), deposit=Sourced(30_000_000, Source.ASSUMED, "가정"),
        monthly_rent=Sourced(3_000_000, Source.AREA_AVG, "기타 평균"), key_money=Sourced(0, Source.ASSUMED),
        startup_cost=Sourced(80_000_000, Source.FRANCHISE, "공정위"), monthly_payroll=Sourced(0, Source.ASSUMED),
        cost_ratio=Sourced(0.3, Source.ASSUMED), loan_rate=Sourced(4.5, Source.ECOS),
        desired_loan=Sourced(0, Source.ASSUMED), expected_monthly_sales=Sourced(15_000_000, Source.AREA_AVG),
    ))
    return AreaFinanceView(1001, "성수동카페거리", "성동구", "CS100010", "커피-음료", plan,
                           RentBenchmark(20262, 45_000, 3.0, "기타", "zone"), "첫 줄", "가정: …")


class _StubUseCase:
    def __init__(self, view):
        self.view, self.queries = view, []

    async def calculate(self, query):
        self.queries.append(query)
        return self.view


async def test_뷰를_허브_DTO로_옮기고_요청_필드를_그대로_넘긴다():
    uc = _StubUseCase(_view())
    info = await AreaFinanceGateway(uc).plan(AreaFinanceRequest(
        1001, "CS100010", 100_000_000, monthly_rent=3_000_000, sources={"equity": "profile"}, equity_note="밴드 중앙"))
    q = uc.queries[0]
    assert q.monthly_rent == 3_000_000 and q.sources == {"equity": "profile"} and q.equity_note == "밴드 중앙"
    assert info.headline == "첫 줄" and info.rent_level == "zone" and info.expected_monthly_sales == 15_000_000
    assert [i.key for i in info.inputs][:3] == ["equity", "deposit", "monthly_rent"]
    assert info.stress_runway == ((1.0, None), (2.0, None))


async def test_None은_그대로_None():
    assert await AreaFinanceGateway(_StubUseCase(None)).plan(AreaFinanceRequest(1, "CS1", 1)) is None
