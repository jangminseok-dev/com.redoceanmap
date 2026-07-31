from game.app.dtos.settlement_dto import SettlementQuery
from game.app.dtos.store_open_dto import OpenStoreCommand
from game.app.use_cases.settlement_interactor import SettlementInteractor
from game.app.use_cases.store_open_interactor import StoreOpenInteractor
from game.domain.clock.game_epoch import (
    GAME_DAYS_PER_QUARTER,
    QUARTERS_PER_SEASON,
    TICKS_PER_GAME_DAY,
)
from game.tests.app.use_cases.stub_account_repository import StubAccountRepository, StubClock
from game.tests.app.use_cases.stub_store_repository import StubStoreRepository
from game.tests.app.use_cases.test_area_fitness_interactor import _StubProfiles, _profile

USER = 9
QUARTER_TICKS = GAME_DAYS_PER_QUARTER * TICKS_PER_GAME_DAY


def _build(tick: int = 0, profile=None):
    accounts = StubAccountRepository()
    stores = StubStoreRepository(accounts=accounts)
    clock = StubClock(tick)
    profiles = _StubProfiles(_profile() if profile is None else profile)
    return (
        StoreOpenInteractor(profiles=profiles, stores=stores, accounts=accounts, clock=clock),
        SettlementInteractor(stores=stores, clock=clock),
        accounts,
        clock,
    )


def _command(**overrides):
    base = dict(
        user_id=USER,
        trdar_code=1001,
        service_code="CS100010",
        budget_krw=600_000,
        facility_score=300,
        staff_count=2,
        price_factor=1.0,
    )
    base.update(overrides)
    return OpenStoreCommand(**base)


async def test_분기가_끝나기_전에는_정산하지_않는다():
    open_uc, settle_uc, _, clock = _build(tick=0)
    await open_uc.open_store(_command())

    clock.tick = 60 * 60  # 게임 60일
    result = await settle_uc.run_and_list(SettlementQuery(user_id=USER))
    assert result.newly_settled == 0
    assert result.settlements == ()


async def test_분기가_끝나면_정산하고_지갑에_반영한다():
    """여기서 창업이 자산에 연결된다 — 일별 손익은 계산만 되다가 분기에 지갑으로 간다."""
    open_uc, settle_uc, accounts, clock = _build(tick=0)
    await open_uc.open_store(_command())
    cash_before = accounts.wallets[USER]["cash_krw"]

    clock.tick = QUARTER_TICKS  # 게임 90일 = 1분기 종료
    result = await settle_uc.run_and_list(SettlementQuery(user_id=USER))

    assert result.newly_settled == 1
    assert len(result.settlements) == 1
    settlement = result.settlements[0]
    assert settlement.game_quarter == 1
    assert settlement.days_counted == GAME_DAYS_PER_QUARTER
    assert settlement.advices

    assert accounts.wallets[USER]["cash_krw"] == cash_before + settlement.profit_krw
    assert accounts.ledger[-1]["source"] == "settlement"
    accounts.assert_invariant(USER)


async def test_두_번_불러도_다시_정산하지_않는다():
    """조회가 곧 정산 시점이라 멱등성이 곧 정확성이다."""
    open_uc, settle_uc, accounts, clock = _build(tick=0)
    await open_uc.open_store(_command())
    clock.tick = QUARTER_TICKS

    first = await settle_uc.run_and_list(SettlementQuery(user_id=USER))
    cash_after_first = accounts.wallets[USER]["cash_krw"]
    second = await settle_uc.run_and_list(SettlementQuery(user_id=USER))

    assert first.newly_settled == 1
    assert second.newly_settled == 0
    assert len(second.settlements) == 1
    assert accounts.wallets[USER]["cash_krw"] == cash_after_first
    accounts.assert_invariant(USER)


async def test_밀린_분기_세_개를_한_번에_정산해도_순차와_같다():
    """8단계 완료 판정 — 오프라인 진행의 정확성이 여기 걸려 있다."""
    # (A) 한 번에 정산
    open_a, settle_a, accounts_a, clock_a = _build(tick=0)
    await open_a.open_store(_command())
    clock_a.tick = QUARTER_TICKS * 3
    bulk = await settle_a.run_and_list(SettlementQuery(user_id=USER))

    # (B) 분기마다 순차 정산
    open_b, settle_b, accounts_b, clock_b = _build(tick=0)
    await open_b.open_store(_command())
    for quarter in range(1, 4):
        clock_b.tick = QUARTER_TICKS * quarter
        await settle_b.run_and_list(SettlementQuery(user_id=USER))
    sequential = await settle_b.run_and_list(SettlementQuery(user_id=USER))

    assert bulk.newly_settled == 3
    assert [s.game_quarter for s in bulk.settlements] == [1, 2, 3]
    assert bulk.settlements == sequential.settlements
    assert accounts_a.wallets[USER]["cash_krw"] == accounts_b.wallets[USER]["cash_krw"]
    accounts_a.assert_invariant(USER)
    accounts_b.assert_invariant(USER)


async def test_적자_결산에도_지갑은_음수가_되지_않는다():
    """파산 없음 — 실패는 기회 손실이지 게임오버가 아니다."""
    bad = _profile(
        floating_age_share=(0.02, 0.05, 0.10, 0.18, 0.40, 0.25),
        floating_hour_share=(0.20, 0.05, 0.06, 0.09, 0.25, 0.35),
        saturation_percentile=0.98,
        closure_rate_percentile=0.98,
        operating_months_percentile=0.02,
    )
    open_uc, settle_uc, accounts, clock = _build(tick=0, profile=bad)
    await open_uc.open_store(_command(budget_krw=800_000))

    clock.tick = QUARTER_TICKS * QUARTERS_PER_SEASON
    result = await settle_uc.run_and_list(SettlementQuery(user_id=USER))

    assert any(s.profit_krw < 0 for s in result.settlements)
    assert accounts.wallets[USER]["cash_krw"] >= 0
    accounts.assert_invariant(USER)


async def test_시즌_전체를_정산하면_여덟_분기다():
    open_uc, settle_uc, _, clock = _build(tick=0)
    await open_uc.open_store(_command())

    clock.tick = QUARTER_TICKS * 20  # 시즌을 한참 넘겨도
    result = await settle_uc.run_and_list(SettlementQuery(user_id=USER))
    assert result.newly_settled == QUARTERS_PER_SEASON
    assert result.season_over is True


async def test_성과배율과_손님수가_함께_나온다():
    open_uc, settle_uc, _, clock = _build(tick=0)
    await open_uc.open_store(_command())
    clock.tick = QUARTER_TICKS

    settlement = (await settle_uc.run_and_list(SettlementQuery(user_id=USER))).settlements[0]
    assert settlement.customer_count > 0
    assert settlement.performance_ratio > 0
    assert 0.0 <= settlement.average_turned_away_ratio <= 1.0
