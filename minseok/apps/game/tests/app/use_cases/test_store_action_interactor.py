"""운영 액션 — 가격·직원·시설 조정과 폐업.

핵심 계약 두 가지를 여기서 지킨다.
1. **과거는 바뀌지 않는다** — 결정을 바꿔도 이미 지나간 날의 손익이 그대로여야 확정된
   분기 결산과 어긋나지 않는다.
2. **원장 불변식** — 시설 추가투자·보증금 환급도 지갑과 원장이 함께 움직여야 한다.
"""
import pytest

from game.app.dtos.store_action_dto import CloseStoreCommand, StoreDecisionCommand
from game.app.dtos.store_daily_dto import StoreDailyQuery
from game.app.dtos.store_open_dto import OpenStoreCommand
from game.app.exceptions import InsufficientCash, InvalidOrder, SeasonClosed, StoreNotFound
from game.app.use_cases.store_action_interactor import StoreActionInteractor
from game.app.use_cases.store_daily_interactor import StoreDailyInteractor
from game.app.use_cases.store_open_interactor import StoreOpenInteractor
from game.domain.clock.game_epoch import SEASON_TICKS, TICKS_PER_GAME_DAY
from game.tests.app.use_cases.stub_account_repository import StubAccountRepository, StubClock
from game.tests.app.use_cases.stub_store_repository import StubStoreRepository
from game.tests.app.use_cases.test_area_fitness_interactor import _StubProfiles, _profile

USER = 7
OPEN_TICK = 600  # 게임 10일차


def _build(tick: int = OPEN_TICK):
    accounts = StubAccountRepository()
    stores = StubStoreRepository(accounts=accounts)
    clock = StubClock(tick)
    profiles = _StubProfiles(_profile())
    return (
        StoreOpenInteractor(profiles=profiles, stores=stores, accounts=accounts, clock=clock),
        StoreActionInteractor(stores=stores, accounts=accounts, clock=clock),
        StoreDailyInteractor(stores=stores, clock=clock),
        accounts,
        clock,
    )


async def _open(open_uc, budget_krw: int = 700_000):
    return await open_uc.open_store(
        OpenStoreCommand(
            user_id=USER,
            trdar_code=1001,
            service_code="CS100010",
            budget_krw=budget_krw,
            staff_count=2,
            price_factor=1.0,
        )
    )


# --- 결정 -------------------------------------------------------------------

async def test_결정은_내일부터_적용된다():
    """오늘 이전을 바꾸면 이미 확정된 분기 결산과 재계산이 어긋난다."""
    open_uc, action_uc, _, _, clock = _build()
    store = await _open(open_uc)

    receipt = await action_uc.decide(
        StoreDecisionCommand(user_id=USER, store_id=store.store_id, price_factor=1.2)
    )
    assert receipt.effective_from_day == 10 + 1
    assert receipt.price_factor == 1.2


async def test_지정하지_않은_항목은_직전_결정을_잇는다():
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc)

    receipt = await action_uc.decide(
        StoreDecisionCommand(user_id=USER, store_id=store.store_id, staff_count=5)
    )
    assert receipt.staff_count == 5
    assert receipt.price_factor == 1.0  # 창업 때 값
    assert receipt.facility_score == store.facility_score


async def test_결정을_바꿔도_과거_손익은_1원도_변하지_않는다():
    """이게 깨지면 확정된 분기 결산이 사후에 틀린 값이 된다."""
    open_uc, action_uc, daily_uc, _, clock = _build()
    store = await _open(open_uc)

    before = await daily_uc.get_daily(StoreDailyQuery(user_id=USER, store_id=store.store_id, days=14))
    past = {r.game_day: r.profit_krw for r in before.rows}

    await action_uc.decide(
        StoreDecisionCommand(user_id=USER, store_id=store.store_id, price_factor=1.3, staff_count=8)
    )
    clock.tick = OPEN_TICK + 5 * TICKS_PER_GAME_DAY  # 5게임일 뒤
    after = await daily_uc.get_daily(StoreDailyQuery(user_id=USER, store_id=store.store_id, days=14))

    for row in after.rows:
        if row.game_day in past:
            assert row.profit_krw == past[row.game_day], f"{row.game_day}일차 손익이 바뀌었다"


async def test_시설_추가투자는_지갑에서_빠지고_원장에_남는다():
    open_uc, action_uc, _, accounts, _ = _build()
    store = await _open(open_uc)
    cash_before = accounts.wallets[USER]["cash_krw"]

    receipt = await action_uc.decide(
        StoreDecisionCommand(
            user_id=USER, store_id=store.store_id, facility_score=store.facility_score + 20
        )
    )
    assert receipt.facility_added == 20
    assert receipt.interior_cost_krw > 0
    assert accounts.wallets[USER]["cash_krw"] == cash_before - receipt.interior_cost_krw
    assert accounts.ledger[-1]["source"] == "store"
    accounts.assert_invariant(USER)


async def test_시설은_줄일_수_없다():
    """되팔 수 없는 지출이라 줄이기를 허용하면 인테리어비를 환급해야 한다."""
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc)
    with pytest.raises(InvalidOrder):
        await action_uc.decide(
            StoreDecisionCommand(
                user_id=USER, store_id=store.store_id, facility_score=store.facility_score - 1
            )
        )


async def test_돈이_없으면_시설을_못_올린다():
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc, budget_krw=900_000)  # 가용 현금을 거의 다 쓰고 시작한다
    with pytest.raises(InsufficientCash):
        await action_uc.decide(
            StoreDecisionCommand(
                user_id=USER, store_id=store.store_id, facility_score=2_000  # 상한까지
            )
        )


async def test_하루에_두_번_바꿀_수_없다():
    """하루에 수십 행이 쌓이면 재계산이 O(일수 × 결정수)로 커진다."""
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc)
    await action_uc.decide(
        StoreDecisionCommand(user_id=USER, store_id=store.store_id, price_factor=1.1)
    )
    with pytest.raises(InvalidOrder):
        await action_uc.decide(
            StoreDecisionCommand(user_id=USER, store_id=store.store_id, price_factor=1.2)
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"price_factor": 0.5},
        {"price_factor": 1.9},
        {"staff_count": -1},
        {"staff_count": 21},
    ],
)
async def test_범위_밖_값은_거부한다(overrides):
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc)
    with pytest.raises(InvalidOrder):
        await action_uc.decide(
            StoreDecisionCommand(user_id=USER, store_id=store.store_id, **overrides)
        )


async def test_남의_가게는_바꿀_수_없다():
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc)
    with pytest.raises(StoreNotFound):
        await action_uc.decide(
            StoreDecisionCommand(user_id=USER + 1, store_id=store.store_id, price_factor=1.1)
        )


async def test_시즌이_끝나면_운영을_바꿀_수_없다():
    open_uc, action_uc, _, _, clock = _build()
    store = await _open(open_uc)
    clock.tick = SEASON_TICKS + 100
    with pytest.raises(SeasonClosed):
        await action_uc.decide(
            StoreDecisionCommand(user_id=USER, store_id=store.store_id, price_factor=1.1)
        )


# --- 폐업 -------------------------------------------------------------------

async def test_폐업하면_보증금을_돌려받고_인테리어는_잃는다():
    open_uc, action_uc, _, accounts, _ = _build()
    store = await _open(open_uc)
    cash_before = accounts.wallets[USER]["cash_krw"]

    receipt = await action_uc.close(CloseStoreCommand(user_id=USER, store_id=store.store_id))
    assert receipt.deposit_refund_krw == store.deposit_krw
    assert receipt.interior_lost_krw == store.interior_krw
    assert accounts.wallets[USER]["cash_krw"] == cash_before + store.deposit_krw
    accounts.assert_invariant(USER)


async def test_폐업일이_분기_중간이면_정산이_남는다():
    """폐업하면 다음 분기 경계가 오지 않는다 — 결산 조회 때 부분 구간이 확정된다."""
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc)
    receipt = await action_uc.close(CloseStoreCommand(user_id=USER, store_id=store.store_id))
    assert receipt.pending_settlement is True
    assert receipt.closed_game_day == 10


async def test_두_번_폐업할_수_없다():
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc)
    await action_uc.close(CloseStoreCommand(user_id=USER, store_id=store.store_id))
    with pytest.raises(InvalidOrder):
        await action_uc.close(CloseStoreCommand(user_id=USER, store_id=store.store_id))


async def test_폐업한_가게는_운영을_바꿀_수_없다():
    open_uc, action_uc, _, _, _ = _build()
    store = await _open(open_uc)
    await action_uc.close(CloseStoreCommand(user_id=USER, store_id=store.store_id))
    with pytest.raises(InvalidOrder):
        await action_uc.decide(
            StoreDecisionCommand(user_id=USER, store_id=store.store_id, price_factor=1.1)
        )


async def test_시즌이_끝나도_폐업은_된다():
    """막으면 보증금이 영원히 잠긴다 — 포지션 청산과 같은 이유다."""
    open_uc, action_uc, _, _, clock = _build()
    store = await _open(open_uc)
    clock.tick = SEASON_TICKS + 100
    receipt = await action_uc.close(CloseStoreCommand(user_id=USER, store_id=store.store_id))
    assert receipt.deposit_refund_krw > 0


# --- 가게 수 상한 -------------------------------------------------------------

async def test_흑자_결산_없이는_2호점을_못_연다():
    open_uc, _, _, _, _ = _build()
    await _open(open_uc, budget_krw=700_000)
    with pytest.raises(InvalidOrder):
        await _open(open_uc, budget_krw=700_000)
