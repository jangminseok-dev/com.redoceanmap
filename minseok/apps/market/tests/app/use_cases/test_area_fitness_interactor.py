from market.app.dtos.area_demand_profile_dto import AreaDemandProfile
from market.app.dtos.area_fitness_dto import AreaFitnessQuery
from market.app.use_cases.area_fitness_interactor import AreaFitnessInteractor

YOUNG_INDUSTRY = (0.05, 0.55, 0.25, 0.10, 0.03, 0.02)
OLD_STREET = (0.02, 0.05, 0.10, 0.18, 0.40, 0.25)
YOUNG_STREET = (0.06, 0.50, 0.24, 0.12, 0.05, 0.03)
LUNCH = (0.02, 0.10, 0.45, 0.20, 0.18, 0.05)
LATEST = 20254


def _profile(**overrides) -> AreaDemandProfile:
    base = dict(
        trdar_code=1001,
        trdar_name="테스트 상권",
        service_code="CS100010",
        service_name="커피-음료",
        year_quarter=LATEST,
        observed_monthly_sales_amount=600_000_000,
        observed_monthly_sales_count=120_000,
        observed_store_count=20,
        observed_similar_store_count=32,
        observed_closure_rate=3.0,
        observed_operating_months_avg=96.0,
        area_weekday_share=(0.14,) * 7,
        area_hour_share=LUNCH,
        area_gender_share=(0.5, 0.5),
        area_age_share=YOUNG_INDUSTRY,
        floating_total=500_000,
        floating_hour_share=LUNCH,
        floating_gender_share=(0.5, 0.5),
        floating_age_share=YOUNG_STREET,
        industry_hour_share=LUNCH,
        industry_gender_share=(0.5, 0.5),
        industry_age_share=YOUNG_INDUSTRY,
        saturation_percentile=0.4,
        closure_rate_percentile=0.3,
        operating_months_percentile=0.7,
        has_sales=True,
        has_store=True,
        has_floating=True,
    )
    base.update(overrides)
    return AreaDemandProfile(**base)


class _StubProfiles:
    def __init__(self, profile: AreaDemandProfile | None, latest: int | None = LATEST):
        self.profile = profile
        self.latest = latest
        self.calls: list[tuple] = []

    async def latest_quarter(self):
        return self.latest

    async def get_demand_profile(self, trdar_code, service_code, year_quarter):
        self.calls.append((trdar_code, service_code, year_quarter))
        return self.profile


QUERY = AreaFitnessQuery(trdar_code=1001, service_code="CS100010")


async def test_적합도와_진단을_함께_낸다():
    result = await AreaFitnessInteractor(profiles=_StubProfiles(_profile())).evaluate(QUERY)

    assert result is not None
    assert result.trdar_name == "테스트 상권"
    assert 0.0 <= result.total_score <= 1.0
    assert [c.key for c in result.components] == [
        "demand_match", "hour_match", "saturation", "survival",
    ]
    assert abs(sum(c.weight for c in result.components) - 1.0) < 1e-9
    assert result.diagnoses  # 문장이 하나는 나온다


async def test_점포당_매출과_객단가는_실데이터에서_유도한다():
    """분모는 유사업종 점포 수 — 추정매출은 프랜차이즈 포함 전체 점포 기준이다(점포_수는 프랜차이즈 제외)."""
    result = await AreaFitnessInteractor(profiles=_StubProfiles(_profile())).evaluate(QUERY)

    assert result.observed_sales_per_store == 600_000_000 // 32
    assert result.observed_ticket_price == 600_000_000 // 120_000


async def test_점포수가_0이어도_나눗셈이_터지지_않는다():
    result = await AreaFitnessInteractor(
        profiles=_StubProfiles(_profile(observed_similar_store_count=0, observed_monthly_sales_count=0))
    ).evaluate(QUERY)
    assert result.observed_sales_per_store == 600_000_000
    assert result.observed_ticket_price == 600_000_000


async def test_최신_적재_분기로_조회한다():
    """game과 달리 분기를 고정하지 않는다 — area_stats·area_ranking과 같은 규칙."""
    stub = _StubProfiles(_profile(), latest=20261)
    await AreaFitnessInteractor(profiles=stub).evaluate(QUERY)
    assert stub.calls[0][2] == 20261


async def test_안_맞는_입지는_점수가_낮고_나쁜_신호가_붙는다():
    good = await AreaFitnessInteractor(profiles=_StubProfiles(_profile())).evaluate(QUERY)
    bad = await AreaFitnessInteractor(
        profiles=_StubProfiles(
            _profile(
                floating_age_share=OLD_STREET,
                floating_hour_share=(0.20, 0.05, 0.06, 0.09, 0.25, 0.35),
                saturation_percentile=0.95,
                closure_rate_percentile=0.95,
                operating_months_percentile=0.05,
            )
        )
    ).evaluate(QUERY)

    assert bad.total_score < good.total_score
    assert any(d.tone == "bad" for d in bad.diagnoses)


async def test_점포_자료가_없으면_경쟁_여유를_만점으로_주지_않는다():
    result = await AreaFitnessInteractor(
        profiles=_StubProfiles(
            _profile(
                observed_monthly_sales_amount=0,
                observed_monthly_sales_count=0,
                observed_store_count=0,
                has_sales=False,
                has_store=False,
            )
        )
    ).evaluate(QUERY)
    assert {c.key: c.score for c in result.components}["saturation"] == 0.5


async def test_자료가_없으면_None을_낸다():
    """상권·업종 부재와 적재 전(분기 None) 둘 다 — HTTP 404 변환은 라우터 몫."""
    assert await AreaFitnessInteractor(profiles=_StubProfiles(None)).evaluate(QUERY) is None
    assert (
        await AreaFitnessInteractor(profiles=_StubProfiles(_profile(), latest=None)).evaluate(QUERY)
        is None
    )
