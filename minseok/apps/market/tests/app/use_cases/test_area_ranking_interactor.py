import pytest

from market.app.dtos.area_ranking_dto import AreaRankingQuery
from market.app.ports.output.area_ranking_repository import (
    AreaMeta,
    SalesAgg,
    ServiceRef,
    StoreAgg,
)
from market.app.use_cases import area_ranking_interactor as mod
from market.app.use_cases.area_ranking_interactor import AreaRankingInteractor


def _meta(
    code: int, gu: str = "성동구", division: str = "A", division_name: str = "골목상권"
) -> AreaMeta:
    return AreaMeta(
        trdar_code=code, trdar_name=f"상권{code}", district_name=gu, dong_name="성수동",
        division_code=division, division_name=division_name, lat=37.5, lng=127.0,
        area_size=71928.0,
    )


class _StubRepo:
    def __init__(self, latest=20254, areas=None, sales=None, stores=None, first=20211):
        self._latest = latest
        self._first = first
        self._areas = areas if areas is not None else [_meta(1)]
        self._sales = sales or []
        self._stores = stores or []
        self.area_filters: tuple | None = None
        self.sales_args: tuple | None = None
        self.store_args: tuple | None = None
        self.range_calls = 0
        self.area_calls = 0

    async def latest_quarter(self):
        return self._latest

    async def quarter_range(self):
        self.range_calls += 1
        return None if self._latest is None else (self._first, self._latest)

    async def find_areas(self, district_name, division_code):
        self.area_filters = (district_name, division_code)
        self.area_calls += 1
        return self._areas

    async def find_sales(self, quarters, service_code):
        self.sales_args = (list(quarters), service_code)
        return self._sales

    async def find_stores(self, year_quarter, service_code):
        self.store_args = (year_quarter, service_code)
        return self._stores

    async def list_service_codes(self, year_quarter):
        return [ServiceRef(code="CS100010", name="커피-음료")]


async def test_점포당_매출과_전분기_대비_변화율을_계산한다():
    repo = _StubRepo(
        sales=[SalesAgg(1, 20254, 1_200_000_000), SalesAgg(1, 20253, 1_000_000_000)],
        stores=[StoreAgg(1, store_count=40, closure_rate=2.5)],
    )
    view = await AreaRankingInteractor(repo=repo).list_ranking(AreaRankingQuery())

    row = view.rows[0]
    assert view.year_quarter == 20254
    assert row.monthly_sales == 1_200_000_000
    assert row.sales_per_store == 30_000_000
    assert row.sales_qoq == 20.0


async def test_직전_분기가_연도_경계를_넘어도_이어붙인다():
    repo = _StubRepo(latest=20251)
    await AreaRankingInteractor(repo=repo).list_ranking(AreaRankingQuery())
    assert repo.sales_args[0] == [20251, 20244]  # 20251의 직전은 20244


async def test_점포가_0이면_점포당_매출을_만들지_않는다():  # 0 나눗셈 방어
    repo = _StubRepo(
        sales=[SalesAgg(1, 20254, 500_000)],
        stores=[StoreAgg(1, store_count=0, closure_rate=0.0)],
    )
    view = await AreaRankingInteractor(repo=repo).list_ranking(AreaRankingQuery())
    assert view.rows[0].sales_per_store is None


async def test_직전_분기_매출이_없으면_변화율은_None():
    repo = _StubRepo(sales=[SalesAgg(1, 20254, 500_000)])
    view = await AreaRankingInteractor(repo=repo).list_ranking(AreaRankingQuery())
    assert view.rows[0].sales_qoq is None


async def test_팩트가_없는_상권도_행으로_남는다():
    # 매출·점포가 없다고 목록에서 사라지면 "이 상권은 왜 없지?"가 된다.
    repo = _StubRepo(areas=[_meta(1), _meta(2)], sales=[SalesAgg(1, 20254, 100)])
    view = await AreaRankingInteractor(repo=repo).list_ranking(AreaRankingQuery())
    assert [r.trdar_code for r in view.rows] == [1, 2]
    assert view.rows[1].monthly_sales is None and view.rows[1].store_count is None


async def test_필터가_저장소로_그대로_전달된다():
    repo = _StubRepo()
    await AreaRankingInteractor(repo=repo).list_ranking(AreaRankingQuery(
        district_name="성동구", division_code="A", service_code="CS100010",
    ))
    assert repo.area_filters == ("성동구", "A")
    assert repo.sales_args[1] == "CS100010"
    assert repo.store_args == (20254, "CS100010")


async def test_데이터가_아예_없으면_빈_목록():  # 404 아님 — 화면은 떠야 한다
    view = await AreaRankingInteractor(repo=_StubRepo(latest=None)).list_ranking(
        AreaRankingQuery()
    )
    assert view.rows == [] and view.year_quarter is None


async def test_업종_어휘를_함께_내려보낸다():
    """목록 하나 때문에 라우터를 새로 만들지 않는다 — 이 엔드포인트 자신의 필터 어휘다."""
    view = await AreaRankingInteractor(repo=_StubRepo()).list_ranking(AreaRankingQuery())
    assert [(s.code, s.name) for s in view.services] == [("CS100010", "커피-음료")]


async def test_데이터가_없으면_업종_어휘도_비어있다():
    view = await AreaRankingInteractor(repo=_StubRepo(latest=None)).list_ranking(AreaRankingQuery())
    assert view.services == []


# ── 쇼케이스 — 비로그인 첫 화면(인증 없이 나가는 유일한 조회) ────────────────


@pytest.fixture(autouse=True)
def _clear_showcase_cache():
    mod._SHOWCASE_CACHE = None
    yield
    mod._SHOWCASE_CACHE = None


def _showcase_repo(specs, latest=20254, first=20211):
    """(코드, 자치구, 유형, 매출, 점포수) 목록으로 스텁을 만든다."""
    return _StubRepo(
        latest=latest,
        first=first,
        areas=[_meta(c, gu=gu, division_name=div) for c, gu, div, _, _ in specs],
        sales=[SalesAgg(c, latest, sales) for c, _, _, sales, _ in specs],
        stores=[StoreAgg(c, store_count=n, closure_rate=1.0) for c, _, _, _, n in specs],
    )


async def test_점포당_매출_내림차순으로_상위만_낸다():
    specs = [(i, f"{i}구", "골목상권", i * 100_000_000, 10) for i in range(1, 12)]
    view = await AreaRankingInteractor(repo=_showcase_repo(specs)).showcase()

    assert len(view.rows) == mod.SHOWCASE_LIMIT
    values = [r.sales_per_store for r in view.rows]
    assert values == sorted(values, reverse=True)
    assert view.rows[0].trdar_code == 11  # 매출이 가장 큰 상권


async def test_점포수가_하한에_못_미치면_제외한다():
    # 점포 1~2개짜리는 점포당 매출이 극단으로 튀어 첫 화면을 통째로 왜곡한다
    view = await AreaRankingInteractor(repo=_showcase_repo([
        (1, "성동구", "골목상권", 90_000_000_000, mod.MIN_STORE_COUNT - 1),
        (2, "마포구", "골목상권", 1_000_000_000, mod.MIN_STORE_COUNT),
    ])).showcase()

    assert [r.trdar_code for r in view.rows] == [2]
    assert view.min_store_count == mod.MIN_STORE_COUNT  # 프론트가 하드코딩하지 않게


async def test_점포당_매출이_없는_상권은_제외한다():
    repo = _StubRepo(areas=[_meta(1), _meta(2, gu="마포구")],
                     sales=[SalesAgg(2, 20254, 1_000_000_000)],
                     stores=[StoreAgg(2, store_count=20, closure_rate=1.0)])
    view = await AreaRankingInteractor(repo=repo).showcase()
    assert [r.trdar_code for r in view.rows] == [2]


async def test_자치구당_한_곳만_남긴다():
    # 이게 없으면 상위 8장이 한 자치구의 도매시장으로 채워진다(실측)
    view = await AreaRankingInteractor(repo=_showcase_repo([
        (1, "동대문구", "전통시장", 9_000_000_000, 10),
        (2, "동대문구", "전통시장", 8_000_000_000, 10),
        (3, "마포구", "골목상권", 1_000_000_000, 10),
    ])).showcase()

    assert [r.trdar_code for r in view.rows] == [1, 3]
    assert [r.district_name for r in view.rows] == ["동대문구", "마포구"]


async def test_유형별_중앙값은_자치구_중복제거_전_전체를_쓴다():
    """카드에서 잘린 상권도 중앙값에는 들어간다 — 상위 카드의 극단값을 읽는 자다."""
    view = await AreaRankingInteractor(repo=_showcase_repo([
        (1, "동대문구", "전통시장", 9_000_000_000, 10),   # 점포당 9억
        (2, "중구", "전통시장", 3_000_000_000, 10),        # 3억
        (3, "종로구", "전통시장", 1_000_000_000, 10),      # 1억
        (4, "마포구", "골목상권", 200_000_000, 10),        # 2천만
    ])).showcase()

    medians = {d.division_name: d for d in view.division_medians}
    assert medians["전통시장"].area_count == 3
    assert medians["전통시장"].median_sales_per_store == 300_000_000
    assert medians["골목상권"].area_count == 1
    # 표본이 많은 유형이 앞에 온다
    assert view.division_medians[0].division_name == "전통시장"


async def test_보유_분기_범위와_상권_수를_함께_낸다():
    specs = [(1, "성동구", "골목상권", 1_000_000_000, 10)]
    repo = _showcase_repo(specs, latest=20254, first=20211)
    repo._areas.append(_meta(99, gu="강남구"))  # 팩트 없는 상권도 총계에는 든다

    view = await AreaRankingInteractor(repo=repo).showcase()
    assert (view.quarter_from, view.year_quarter) == (20211, 20254)
    assert view.area_count == 2


async def test_데이터가_아예_없으면_빈_쇼케이스():
    view = await AreaRankingInteractor(repo=_StubRepo(latest=None)).showcase()
    assert view.rows == [] and view.division_medians == []
    assert view.year_quarter is None and view.area_count == 0


async def test_같은_분기면_재집계하지_않는다():
    # 인증도 rate limit도 없는 엔드포인트다 — 캐시가 DB 증폭을 막는 유일한 방어선
    repo = _showcase_repo([(1, "성동구", "골목상권", 1_000_000_000, 10)])
    interactor = AreaRankingInteractor(repo=repo)

    first = await interactor.showcase()
    second = await interactor.showcase()

    assert second is first          # 같은 객체 — 재계산조차 하지 않았다
    assert repo.area_calls == 1     # 비싼 집계는 1회
    assert repo.range_calls == 2    # 버전 확인만 매번(index-only scan)


async def test_분기가_바뀌면_다시_집계한다():
    repo = _showcase_repo([(1, "성동구", "골목상권", 1_000_000_000, 10)])
    interactor = AreaRankingInteractor(repo=repo)

    await interactor.showcase()
    repo._latest = 20261  # 새 분기 적재
    view = await interactor.showcase()

    assert view.year_quarter == 20261
    assert repo.area_calls == 2


async def test_데이터가_없으면_캐시하지_않는다():
    # 빈 응답을 캐시하면 적재가 들어와도 영영 빈 화면이 남는다
    repo = _StubRepo(latest=None)
    interactor = AreaRankingInteractor(repo=repo)

    await interactor.showcase()
    assert mod._SHOWCASE_CACHE is None
