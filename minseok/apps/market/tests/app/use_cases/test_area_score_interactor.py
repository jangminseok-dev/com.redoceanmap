from market.app.dtos.area_score_dto import AreaScoreHeader, AreaScoreQuery
from market.app.use_cases.area_score_interactor import AreaScoreInteractor
from market.domain.value_objects.area_score_vo import AreaScoreInputs, QuarterValue


def _qv(yq, value):
    return QuarterValue(year_quarter=yq, value=value)


class _StubRepo:
    def __init__(self, header=None, sales=None, floating=None, inputs=None, medians=None):
        self.header = header
        self.sales = sales or []
        self.floating = floating or []
        self.inputs = inputs
        self.medians = medians
        self.medians_requested: str | None = None

    async def find_header(self, trdar_code):
        return self.header

    async def find_sales_series(self, trdar_code, quarters):
        return self.sales

    async def find_floating_series(self, trdar_code, quarters):
        return self.floating

    async def find_score_inputs(self, trdar_code):
        return self.inputs

    async def find_city_score_medians(self, sido_code):
        self.medians_requested = sido_code
        return self.medians


_INPUTS = AreaScoreInputs(year_quarter=20262, closure_rate_4q=1.5, operating_months=125.0,
                          sales_per_store_wan=2000.0)
_MEDIANS = AreaScoreInputs(year_quarter=20262, closure_rate_4q=3.0, operating_months=100.0,
                           sales_per_store_wan=1000.0)
_HEADER = AreaScoreHeader(
    trdar_code=1000123, trdar_name="성수동 카페거리", district_name="성동구", sido_code="11",
)


async def test_상권이_없으면_None을_반환한다():
    view = await AreaScoreInteractor(repo=_StubRepo()).get_score(AreaScoreQuery(trdar_code=999))
    assert view is None


async def test_3개_컴포넌트를_서울_중앙값과_비교해_채점한다():
    repo = _StubRepo(header=_HEADER, inputs=_INPUTS, medians=_MEDIANS)
    view = await AreaScoreInteractor(repo=repo).get_score(AreaScoreQuery(trdar_code=1000123))

    by_key = {c.key: c for c in view.score.components}
    assert set(by_key) == {"closure_stability", "persistence", "sales_level"}
    assert by_key["closure_stability"].score == 75.0  # 1.5% vs 중앙 3% → -1.5%p / 캡 3
    assert by_key["persistence"].score == 75.0       # 상대비 +25% / 캡 50%
    assert by_key["sales_level"].score == 100.0      # 중앙값의 2배
    assert by_key["closure_stability"].value == 1.5 and by_key["closure_stability"].benchmark == 3.0
    assert view.score.total == 77.5  # 0.55·75 + 0.35·75 + 0.10·100 (2026-09-18 재적합 가중치)
    assert view.score.grade == "양호"   # 80점 미만 — 매출 축 비중이 줄어 같은 입력의 총점이 80.5 → 77.5
    assert repo.medians_requested == "11"


async def test_산출_불가_축은_가중치째_빠진다():
    partial = AreaScoreInputs(year_quarter=20262, closure_rate_4q=None, operating_months=125.0,
                              sales_per_store_wan=None)  # 점포 5개 미만 상권
    view = await AreaScoreInteractor(repo=_StubRepo(header=_HEADER, inputs=partial, medians=_MEDIANS)).get_score(
        AreaScoreQuery(trdar_code=1000123)
    )
    assert [c.key for c in view.score.components] == ["persistence"]
    assert view.score.total == 75.0


async def test_추이는_매출과_유동인구를_분기_축으로_병합한다():
    repo = _StubRepo(
        header=_HEADER,
        sales=[_qv(20253, 100), _qv(20254, 110)],
        floating=[_qv(20252, 900), _qv(20253, 1000)],
    )
    view = await AreaScoreInteractor(repo=repo).get_score(AreaScoreQuery(trdar_code=1000123))

    assert [p.year_quarter for p in view.trend] == [20252, 20253, 20254]
    assert view.trend[0].monthly_sales is None
    assert view.trend[1].monthly_sales == 100
    assert view.trend[1].floating_qoq == 11.11
    assert view.trend[2].sales_qoq == 10.0
    assert view.trend[2].total_floating_pop is None


async def test_팩트가_전혀_없으면_score가_None인_view를_반환한다():
    view = await AreaScoreInteractor(repo=_StubRepo(header=_HEADER)).get_score(
        AreaScoreQuery(trdar_code=1000123)
    )
    assert view is not None
    assert view.score is None
    assert view.trend == []


async def test_시도_코드가_없으면_중앙값이_없어_score가_None이다():
    repo = _StubRepo(
        header=AreaScoreHeader(trdar_code=1, trdar_name="미연결 상권", district_name="", sido_code=None),
        sales=[_qv(20253, 100), _qv(20254, 110)], inputs=_INPUTS, medians=_MEDIANS,
    )
    view = await AreaScoreInteractor(repo=repo).get_score(AreaScoreQuery(trdar_code=1))
    assert view.score is None
    assert repo.medians_requested is None
    assert len(view.trend) == 2  # 추이는 벤치마크 없이도 제공
