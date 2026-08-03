import pytest

from game.app.dtos.store_daily_dto import StoreDailyQuery
from game.app.dtos.store_open_dto import OpenStoreCommand
from game.app.exceptions import (
    AreaProfileUnavailable,
    InsufficientCash,
    InvalidOrder,
    SeasonClosed,
    StoreNotFound,
)
from game.app.use_cases.store_daily_interactor import StoreDailyInteractor
from game.app.use_cases.store_open_interactor import StoreOpenInteractor
from game.domain.clock.game_epoch import DATA_QUARTER, SEASON_TICKS
from game.domain.trading.trading_rules import INITIAL_CASH_KRW
from game.tests.app.use_cases.stub_account_repository import StubAccountRepository, StubClock
from game.tests.app.use_cases.stub_store_repository import StubStoreRepository
from game.tests.app.use_cases.test_area_fitness_interactor import _StubProfiles, _profile

USER = 5


def _build(tick: int = 600, profile=None):
    accounts = StubAccountRepository()
    stores = StubStoreRepository(accounts=accounts)
    clock = StubClock(tick)
    profiles = _StubProfiles(_profile() if profile is None else profile)
    return (
        StoreOpenInteractor(profiles=profiles, stores=stores, accounts=accounts, clock=clock),
        StoreDailyInteractor(stores=stores, clock=clock),
        accounts,
        clock,
    )


def _command(**overrides):
    base = dict(
        user_id=USER,
        trdar_code=1001,
        service_code="CS100010",
        budget_krw=700_000,
        staff_count=2,
        price_factor=1.0,
    )
    base.update(overrides)
    return OpenStoreCommand(**base)


# --- 창업 -------------------------------------------------------------------

async def test_창업하면_보증금과_인테리어가_빠지고_원장에_남는다():
    open_uc, _, accounts, _ = _build()
    receipt = await open_uc.open_store(_command())

    assert receipt.cash_delta_krw < 0
    assert receipt.deposit_krw > 0 and receipt.interior_krw > 0
    assert receipt.cash_krw == INITIAL_CASH_KRW + receipt.cash_delta_krw
    assert accounts.ledger[-1]["source"] == "store"
    accounts.assert_invariant(USER)


async def test_투입_자본이_규모를_정한다():
    """상권 평균 점포는 수천만 원이라 초기 자본으로는 작게 시작할 수밖에 없다."""
    small_uc, _, _, _ = _build()
    small = await small_uc.open_store(_command(budget_krw=600_000))

    big_uc, _, _, _ = _build()
    big = await big_uc.open_store(_command(budget_krw=900_000))
    assert big.store_scale > small.store_scale


async def test_에포크에_박힌_분기로_상권을_읽는다():
    open_uc, _, _, _ = _build()
    await open_uc.open_store(_command())
    assert open_uc._profiles.calls[0][2] == DATA_QUARTER


async def test_자본이_최소_가게값에도_못_미치면_거부한다():
    """규모에 하한이 있어 자본이 너무 적으면 비용이 투입 자본을 넘는다 — 그때는 거부한다.

    조용히 더 청구하면 유저가 넣겠다고 한 금액과 실제 지출이 갈라진다.
    """
    open_uc, _, _, _ = _build()
    with pytest.raises(InsufficientCash):
        await open_uc.open_store(_command(budget_krw=10_000))


async def test_요청한_자본보다_많이_청구하지_않는다():
    open_uc, _, _, _ = _build()
    receipt = await open_uc.open_store(_command(budget_krw=700_000))
    assert -receipt.cash_delta_krw <= 700_000


@pytest.mark.parametrize(
    "overrides",
    [
        {"staff_count": -1},
        {"price_factor": 2.0},
        {"budget_krw": 0},
    ],
)
async def test_잘못된_창업_조건은_거부한다(overrides):
    open_uc, _, _, _ = _build()
    with pytest.raises((InvalidOrder, InsufficientCash)):
        await open_uc.open_store(_command(**overrides))


async def test_없는_상권은_404용_예외를_낸다():
    open_uc, _, _, _ = _build(profile=False)
    open_uc._profiles.profile = None
    with pytest.raises(AreaProfileUnavailable):
        await open_uc.open_store(_command())


async def test_매출_기록이_없는_조합은_창업_기준을_세울_수_없다():
    open_uc, _, _, _ = _build(profile=_profile(observed_monthly_sales_amount=0))
    with pytest.raises(AreaProfileUnavailable):
        await open_uc.open_store(_command())


async def test_시즌이_끝나면_창업할_수_없다():
    open_uc, _, _, _ = _build(tick=SEASON_TICKS + 100)
    with pytest.raises(SeasonClosed):
        await open_uc.open_store(_command())


# --- 일일 현황 ---------------------------------------------------------------

async def test_접속하지_않은_동안에도_가게는_장사한다():
    """오프라인 진행 — 며칠 뒤 열어보면 그동안의 매출이 이미 쌓여 있다."""
    open_uc, daily_uc, _, clock = _build(tick=600)  # 게임 10일차
    receipt = await open_uc.open_store(_command())

    clock.tick = 600 + 60 * 20  # 게임 20일 경과
    view = await daily_uc.get_daily(
        StoreDailyQuery(user_id=USER, store_id=receipt.store_id, days=30)
    )
    assert view.days_open == 21
    assert view.cumulative_sales_krw > 0
    assert len(view.rows) == 21


async def test_손님은_상권_분포에서_생성된다():
    open_uc, daily_uc, _, clock = _build()
    receipt = await open_uc.open_store(_command())
    clock.tick += 60 * 5

    view = await daily_uc.get_daily(
        StoreDailyQuery(user_id=USER, store_id=receipt.store_id, days=7)
    )
    assert view.customers_by_age and view.customers_by_hour and view.customers_by_taste
    assert sum(b.count for b in view.customers_by_age) == 40


async def test_같은_시점을_두_번_조회하면_같다():
    """일별 매출을 저장하지 않으므로 재계산이 안정적이어야 한다."""
    open_uc, daily_uc, _, clock = _build()
    receipt = await open_uc.open_store(_command())
    clock.tick += 60 * 10

    query = StoreDailyQuery(user_id=USER, store_id=receipt.store_id, days=10)
    assert await daily_uc.get_daily(query) == await daily_uc.get_daily(query)


async def test_가게_목록에_누적_손익이_나온다():
    open_uc, daily_uc, _, clock = _build()
    await open_uc.open_store(_command())
    clock.tick += 60 * 30

    stores = await daily_uc.list_stores(USER)
    assert len(stores) == 1
    assert stores[0].days_open == 31
    assert stores[0].cumulative_sales_krw > 0


async def test_시즌이_끝나면_시뮬레이션도_멈춘다():
    open_uc, daily_uc, _, clock = _build(tick=600)
    receipt = await open_uc.open_store(_command())

    clock.tick = SEASON_TICKS + 60 * 100
    view = await daily_uc.get_daily(
        StoreDailyQuery(user_id=USER, store_id=receipt.store_id, days=90)
    )
    season_last_day = (SEASON_TICKS - 1) // 60
    assert view.rows[-1].game_day == season_last_day


async def test_남의_가게는_보이지_않는다():
    open_uc, daily_uc, _, _ = _build()
    receipt = await open_uc.open_store(_command())

    with pytest.raises(StoreNotFound):
        await daily_uc.get_daily(
            StoreDailyQuery(user_id=USER + 1, store_id=receipt.store_id, days=7)
        )
    assert await daily_uc.list_stores(USER + 1) == ()
