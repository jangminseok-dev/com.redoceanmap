"""공개 상권 페이지(A-4) — 비로그인에게 나가는 뷰는 **필드를 명시적으로 고른다**.

상세·점수 유스케이스를 조합만 하고 새 집계는 없다. 좌표·인허가 상호·인구 피라미드·업종
랭킹 표는 뷰에 존재하지 않아야 한다(있으면 라우터가 실수로 내보낼 수 있다).
"""
import dataclasses

from market.app.dtos.area_detail_dto import AreaDetailView
from market.app.dtos.area_public_dto import AreaIndexRow, AreaPublicView
from market.app.dtos.area_score_dto import AreaScoreView
from market.app.use_cases.area_public_interactor import AreaPublicInteractor
from market.domain.value_objects.area_profile_vo import FloatingRhythm, ServiceRank
from market.domain.value_objects.area_score_vo import AreaScore, ScoreComponent
from market.domain.value_objects.insight_vo import Insight

_META = AreaIndexRow(trdar_code=1000123, trdar_name="성수동 카페거리", district_name="성동구",
                     division_name="골목상권")


class _StubIndex:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def find_one(self, trdar_code):
        return next((r for r in self.rows if r.trdar_code == trdar_code), None)

    async def list_all(self):
        return list(self.rows)


class _StubDetail:
    def __init__(self, view=None):
        self.view = view
        self.called_with = None

    async def get_detail(self, query):
        self.called_with = query
        return self.view


class _StubScore:
    def __init__(self, view=None):
        self.view = view

    async def get_score(self, query):
        return self.view


def _detail_view():
    return AreaDetailView(
        trdar_code=1000123, trdar_name="성수동 카페거리", district_name="성동구",
        service_code="CS100010", service_name="커피-음료",
        sales_mix=None, resident=None, working=None, apartment=None, spending=None,
        floating=FloatingRhythm(year_quarter=20261, weekday_pop=650_000, weekend_pop=180_000),
        facility=None, permit_churn=None,
        service_ranking=[
            ServiceRank(code="CS100001", name="한식음식점", monthly_sales=900_000_000,
                        store_count=120, sales_per_store=7_500_000, sales_qoq=1.0, closure_rate=3.0),
            ServiceRank(code="CS100010", name="커피-음료", monthly_sales=356_500_000,
                        store_count=46, sales_per_store=7_750_000, sales_qoq=3.9, closure_rate=2.1),
        ],
        insights=[Insight(key="payback", tone="neutral", text="회수 약 5.8년")],
    )


def _score_view():
    return AreaScoreView(
        trdar_code=1000123, trdar_name="성수동 카페거리", district_name="성동구",
        score=AreaScore(total=67.0, grade="양호", components=(
            ScoreComponent(key="sales_growth", name="매출 성장", score=70.0, value=3.9, benchmark=1.2),
        )),
        trend=[],
    )


def _interactor(index=None, detail=None, score=None):
    return AreaPublicInteractor(
        index=index or _StubIndex([_META]),
        detail=detail or _StubDetail(_detail_view()),
        score=score or _StubScore(_score_view()),
    )


async def test_상권이_없으면_None():
    assert await _interactor(index=_StubIndex([])).get_public(999) is None


async def test_공개_뷰는_허용_필드만_가진다():
    fields = {f.name for f in dataclasses.fields(AreaPublicView)}
    assert fields == {
        "trdar_code", "trdar_name", "district_name", "division_name", "year_quarter",
        "score", "service_code", "service_name", "store_count", "sales_per_store",
        "sales_qoq", "closure_rate", "floating_pop", "insights",
    }


async def test_기준_업종_행에서_핵심_지표를_고르고_점수와_해석을_싣는다():
    detail = _StubDetail(_detail_view())
    view = await _interactor(detail=detail).get_public(1000123)

    assert detail.called_with.trdar_code == 1000123 and detail.called_with.service_code is None
    assert (view.trdar_name, view.district_name, view.division_name) == ("성수동 카페거리", "성동구", "골목상권")
    assert view.year_quarter == 20261
    # 랭킹 1위(한식)가 아니라 **기준 업종(커피)** 행의 값이어야 한다
    assert view.service_name == "커피-음료"
    assert (view.store_count, view.sales_per_store, view.sales_qoq, view.closure_rate) == (46, 7_750_000, 3.9, 2.1)
    assert view.floating_pop == 830_000
    assert view.score.grade == "양호" and view.score.total == 67.0
    assert [i.key for i in view.insights] == ["payback"]


async def test_점수와_업종이_없으면_None으로_열화한다():
    bare = dataclasses.replace(_detail_view(), service_code=None, service_name=None,
                               service_ranking=[], floating=None, insights=[])
    view = await _interactor(detail=_StubDetail(bare), score=_StubScore(None)).get_public(1000123)

    assert view is not None and view.trdar_name == "성수동 카페거리"
    assert view.score is None and view.service_name is None
    assert view.sales_per_store is None and view.floating_pop is None and view.year_quarter is None


async def test_인덱스는_코드_이름_자치구만_나른다():
    rows = await _interactor().list_index()
    assert rows == [_META]
    assert {f.name for f in dataclasses.fields(AreaIndexRow)} == {
        "trdar_code", "trdar_name", "district_name", "division_name",
    }
