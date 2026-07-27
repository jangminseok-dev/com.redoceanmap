from market.app.dtos.area_detail_dto import AreaDetailQuery
from market.app.dtos.area_stats_dto import AreaHeader, ServiceRef
from market.app.use_cases.area_detail_interactor import AreaDetailInteractor
from market.domain.value_objects.area_profile_vo import (
    ResidentProfile,
    SalesMix,
    WorkingProfile,
)


def _sales_mix():
    return SalesMix(
        year_quarter=20244,
        weekday_amount=850, weekend_amount=150,
        by_day={d: 100 for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        by_time={t: 100 for t in ("t00_06", "t06_11", "t11_14", "t14_17", "t17_21", "t21_24")},
        by_gender={"male": 500, "female": 500},
        by_age={k: 100 for k in ("age10", "age20", "age30", "age40", "age50", "age60Plus")},
        monthly_count=100,
    )


class _StubRepo:
    def __init__(self, header=None, service=None, sales_mix=None,
                 resident=None, working=None, apartment=None, spending=None,
                 floating=None):
        self.header = header
        self.service = service
        self.sales_mix = sales_mix
        self.resident = resident
        self.working = working
        self.apartment = apartment
        self.spending = spending
        self.floating = floating
        self.requested_service: tuple | None = None
        self.sales_mix_called_with: tuple | None = None

    async def find_header(self, trdar_code):
        return self.header

    async def resolve_service(self, trdar_code, service_code):
        self.requested_service = (trdar_code, service_code)
        return self.service

    async def find_sales_mix(self, trdar_code, service_code):
        self.sales_mix_called_with = (trdar_code, service_code)
        return self.sales_mix

    async def find_resident(self, trdar_code):
        return self.resident

    async def find_working(self, trdar_code):
        return self.working

    async def find_apartment(self, trdar_code):
        return self.apartment

    async def find_floating_rhythm(self, trdar_code):
        return self.floating

    async def find_spending(self, trdar_code):
        return self.spending


_HEADER = AreaHeader(trdar_code=1000123, trdar_name="성수동 카페거리", district_name="성동구")


async def test_상권이_없으면_None을_반환한다():
    view = await AreaDetailInteractor(detail=_StubRepo()).get_detail(
        AreaDetailQuery(trdar_code=999)
    )
    assert view is None


async def test_팩트_스냅샷을_조립하고_해석_문장을_붙인다():
    repo = _StubRepo(
        header=_HEADER,
        service=ServiceRef(code="CS100010", name="커피-음료"),
        sales_mix=_sales_mix(),
        resident=ResidentProfile(year_quarter=20244, total=10000, by_age=[],
                                 total_households=100, apartment_households=60),
        working=WorkingProfile(year_quarter=20244, total=30000, by_age=[]),
    )
    view = await AreaDetailInteractor(detail=repo).get_detail(
        AreaDetailQuery(trdar_code=1000123)
    )
    assert view.trdar_name == "성수동 카페거리"
    assert view.service_code == "CS100010"
    assert view.sales_mix.year_quarter == 20244
    keys = {i.key for i in view.insights}
    # 매출 리듬(주중 85%) + 오피스형(3배) + 아파트(60%) 문장이 생성된다
    assert {"sales_rhythm_weekend", "demand_type", "demand_apartment"} <= keys


async def test_업종이_없으면_매출_분해_없이_인구만_담는다():
    repo = _StubRepo(
        header=_HEADER,
        service=None,
        resident=ResidentProfile(year_quarter=20244, total=10000, by_age=[],
                                 total_households=100, apartment_households=10),
    )
    view = await AreaDetailInteractor(detail=repo).get_detail(
        AreaDetailQuery(trdar_code=1000123)
    )
    assert view.service_code is None
    assert view.sales_mix is None
    assert repo.sales_mix_called_with is None  # 업종 미확정이면 매출 조회 자체를 생략
    assert view.resident.total == 10000


async def test_지정한_service_code가_저장소에_전달된다():
    repo = _StubRepo(
        header=_HEADER,
        service=ServiceRef(code="CS100001", name="한식음식점"),
        sales_mix=_sales_mix(),
    )
    await AreaDetailInteractor(detail=repo).get_detail(
        AreaDetailQuery(trdar_code=1000123, service_code="CS100001")
    )
    assert repo.requested_service == (1000123, "CS100001")
    assert repo.sales_mix_called_with == (1000123, "CS100001")


async def test_전_팩트_결측이면_빈_insights로_뷰만_반환한다():
    view = await AreaDetailInteractor(detail=_StubRepo(header=_HEADER)).get_detail(
        AreaDetailQuery(trdar_code=1000123)
    )
    assert view.insights == []
    assert view.sales_mix is None and view.resident is None
