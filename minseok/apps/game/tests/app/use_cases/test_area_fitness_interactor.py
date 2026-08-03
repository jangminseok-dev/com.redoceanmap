import pytest

from game.app.dtos.area_fitness_dto import AreaFitnessQuery
from game.app.exceptions import AreaProfileUnavailable
from game.app.use_cases.area_fitness_interactor import AreaFitnessInteractor
from game.domain.clock.game_epoch import DATA_QUARTER
from hub.app.dtos.area_demand_profile_dto import AreaDemandProfile

YOUNG_INDUSTRY = (0.05, 0.55, 0.25, 0.10, 0.03, 0.02)
OLD_STREET = (0.02, 0.05, 0.10, 0.18, 0.40, 0.25)
YOUNG_STREET = (0.06, 0.50, 0.24, 0.12, 0.05, 0.03)
LUNCH = (0.02, 0.10, 0.45, 0.20, 0.18, 0.05)


def _profile(**overrides) -> AreaDemandProfile:
    base = dict(
        trdar_code=1001,
        trdar_name="테스트 상권",
        service_code="CS100010",
        service_name="커피-음료",
        year_quarter=DATA_QUARTER,
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
    def __init__(self, profile: AreaDemandProfile | None):
        self.profile = profile
        self.calls: list[tuple] = []

    async def get_demand_profile(self, trdar_code, service_code, year_quarter):
        self.calls.append((trdar_code, service_code, year_quarter))
        return self.profile


async def test_적합도와_진단을_함께_낸다():
    interactor = AreaFitnessInteractor(profiles=_StubProfiles(_profile()))
    result = await interactor.preview(AreaFitnessQuery(trdar_code=1001, service_code="CS100010"))

    assert result.trdar_name == "테스트 상권"
    assert 0.4 <= result.fitness <= 1.6
    assert len(result.components) == 4
    assert result.diagnoses  # 문장이 하나는 나온다


async def test_점포당_매출과_객단가는_실데이터에서_유도한다():
    """(분기, 상권, 업종) 축이 일치해야 한다 — similar_industry와 섞으면 안 된다."""
    interactor = AreaFitnessInteractor(profiles=_StubProfiles(_profile()))
    result = await interactor.preview(AreaFitnessQuery(trdar_code=1001, service_code="CS100010"))

    assert result.observed_sales_per_store == 600_000_000 // 20
    assert result.observed_ticket_price == 600_000_000 // 120_000


async def test_점포수가_0이어도_나눗셈이_터지지_않는다():
    interactor = AreaFitnessInteractor(
        profiles=_StubProfiles(_profile(observed_store_count=0, observed_monthly_sales_count=0))
    )
    result = await interactor.preview(AreaFitnessQuery(trdar_code=1001, service_code="CS100010"))
    assert result.observed_sales_per_store == 600_000_000
    assert result.observed_ticket_price == 600_000_000


async def test_에포크에_박힌_분기로_조회한다():
    """market이 새 분기를 적재해도 진행 중인 시즌의 기준선은 바뀌지 않는다."""
    stub = _StubProfiles(_profile())
    await AreaFitnessInteractor(profiles=stub).preview(
        AreaFitnessQuery(trdar_code=1001, service_code="CS100010")
    )
    assert stub.calls[0][2] == DATA_QUARTER


async def test_안_맞는_입지는_기대매출이_낮다():
    """이상한 곳에 이상한 업종 — 이게 이 게임의 핵심 메시지다."""
    good = await AreaFitnessInteractor(profiles=_StubProfiles(_profile())).preview(
        AreaFitnessQuery(trdar_code=1001, service_code="CS100010")
    )
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
    ).preview(AreaFitnessQuery(trdar_code=1001, service_code="CS100010"))

    assert bad.fitness < good.fitness
    assert bad.simulated_monthly_sales_krw < good.simulated_monthly_sales_krw
    assert any(d.tone == "bad" for d in bad.diagnoses)


async def test_매출_기록이_없으면_창업_불가로_알려준다():
    """상권·업종 조합은 있으나 매출 행이 없는 자리 — 서울 실데이터에 흔하다.

    미리보기가 이걸 숨기면 화면은 창업 버튼을 열어주고 유저는 누른 뒤에야 거절당한다.
    """
    interactor = AreaFitnessInteractor(
        profiles=_StubProfiles(
            _profile(
                observed_monthly_sales_amount=0,
                observed_monthly_sales_count=0,
                observed_store_count=0,
                has_sales=False,
                has_store=False,
            )
        )
    )
    result = await interactor.preview(AreaFitnessQuery(trdar_code=1001, service_code="CS100010"))

    assert result.openable is False
    assert result.assumed_minimum_capital_krw == 0
    assert result.assumed_viable_capital_krw == 0
    # 자료 없음이 "경쟁자가 없다"로 둔갑해 만점을 받지 않는다
    assert {c.key: c.score for c in result.components}["saturation"] == 0.5


async def test_창업_가능한_자리는_두_경계를_함께_알려준다():
    """창업이 되는 금액과 손님이 오기 시작하는 금액은 다르다 — 둘을 구분해 보여준다."""
    interactor = AreaFitnessInteractor(profiles=_StubProfiles(_profile()))
    result = await interactor.preview(AreaFitnessQuery(trdar_code=1001, service_code="CS100010"))

    assert result.openable is True
    assert result.assumed_minimum_capital_krw > 0
    # 장사 성립선은 창업 가능선보다 높다 — 반대면 경고가 영원히 뜨지 않는다
    assert result.assumed_viable_capital_krw > result.assumed_minimum_capital_krw


async def test_자료가_없으면_404용_예외를_낸다():
    interactor = AreaFitnessInteractor(profiles=_StubProfiles(None))
    with pytest.raises(AreaProfileUnavailable):
        await interactor.preview(AreaFitnessQuery(trdar_code=999, service_code="CS100010"))
