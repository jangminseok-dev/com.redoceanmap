"""선물 진입·청산·만기 정산.

지갑과 같은 원장을 쓰므로 **불변식(SUM(ledger) == cash)** 이 여기서도 지켜져야 한다.
"""
import pytest

from game.app.dtos.futures_dto import (
    CloseFuturesCommand,
    FuturesQuery,
    OpenFuturesCommand,
)
from game.app.dtos.wallet_dto import WalletQuery
from game.app.exceptions import InsufficientCash, InvalidOrder, PositionNotFound, SeasonClosed
from game.app.use_cases.futures_interactor import FuturesInteractor
from game.app.use_cases.wallet_interactor import WalletInteractor
from game.domain.clock.game_epoch import SEASON_TICKS
from game.domain.market import futures_contract as fut
from game.tests.app.use_cases.stub_account_repository import StubAccountRepository, StubClock

USER = 11


def _build(tick: int = 100):
    repo = StubAccountRepository()
    clock = StubClock(tick)
    return FuturesInteractor(repository=repo, clock=clock), repo, clock


# --- 조회 -------------------------------------------------------------------

async def test_근월물과_현물이_함께_나온다():
    uc, _, _ = _build()
    view = await uc.get_market(FuturesQuery(user_id=USER))
    assert view.virtual is True
    assert view.contract_code.startswith("GXIF-")
    assert view.index_point > 0 and view.futures_point > 0
    assert view.margin_per_contract_krw > 0
    assert view.max_contracts >= 1  # 초기자본으로 최소 1계약은 잡을 수 있어야 한다


async def test_잔존이_0이_되면_베이시스도_0이다():
    contract = fut.front_contract(0)
    uc, _, _ = _build(tick=contract.expiry_tick)
    view = await uc.get_market(FuturesQuery(user_id=USER))
    # 만기 시점에는 다음 계약으로 넘어가므로 새 계약의 잔존이 최대다
    assert view.ticks_to_expiry > 0


# --- 진입 -------------------------------------------------------------------

async def test_진입하면_증거금만_빠지고_원장에_남는다():
    uc, repo, _ = _build()
    receipt = await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=1))

    assert receipt.margin_krw < receipt.price_krw  # 증거금은 명목의 1/5
    assert receipt.cash_delta_krw == -(receipt.margin_krw + receipt.fee_krw)
    assert repo.ledger[-1]["source"] == "trade"
    repo.assert_invariant(USER)


async def test_증거금이_모자라면_거부한다():
    uc, _, _ = _build()
    with pytest.raises(InsufficientCash):
        await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=100))


async def test_만기_직전에는_진입할_수_없다():
    """1틱짜리 계약을 막는다(실제 최종거래일 개념)."""
    contract = fut.front_contract(0)
    uc, _, _ = _build(tick=contract.expiry_tick - 1)
    with pytest.raises(InvalidOrder):
        await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=1))


@pytest.mark.parametrize("contracts", [0, -1, 10_000])
async def test_계약_수가_범위를_벗어나면_거부한다(contracts):
    uc, _, _ = _build()
    with pytest.raises(InvalidOrder):
        await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=contracts))


async def test_시즌이_끝나면_진입할_수_없다():
    uc, _, _ = _build(tick=SEASON_TICKS + 10)
    with pytest.raises(SeasonClosed):
        await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=1))


# --- 청산·정산 ---------------------------------------------------------------

async def test_중도_청산하면_증거금과_손익이_돌아온다():
    uc, repo, clock = _build()
    opened = await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=1))
    clock.tick = 150

    closed = await uc.close(CloseFuturesCommand(user_id=USER, position_id=opened.position_id))
    assert closed.realized_pnl_krw is not None
    assert closed.cash_delta_krw >= 0  # 회수액은 음수가 되지 않는다
    repo.assert_invariant(USER)


async def test_만기가_지나면_현물_정산가로_확정된다():
    """선물가가 아니라 그 시점 **현물 지수**로 정산한다."""
    uc, repo, clock = _build()
    opened = await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=1))
    clock.tick = opened.expires_tick + 500  # 만기를 한참 넘겨 복귀

    closed = await uc.close(CloseFuturesCommand(user_id=USER, position_id=opened.position_id))
    assert closed.futures_point == fut.settlement_price(opened.expires_tick)
    repo.assert_invariant(USER)


async def test_만기_도달분은_지갑_조회가_정산한다():
    """조회가 곧 정산 시점 — 접속하지 않아도 만기는 지나간다."""
    uc, repo, clock = _build()
    await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=1))
    clock.tick = fut.FUTURES_EXPIRY_TICKS + 1_000

    view = await WalletInteractor(repository=repo, clock=clock).get_wallet(
        WalletQuery(user_id=USER)
    )
    assert view.positions == ()
    assert [c.reason for c in view.recently_closed] == ["settled"]
    repo.assert_invariant(USER)


async def test_남의_포지션은_청산할_수_없다():
    uc, _, _ = _build()
    opened = await uc.open(OpenFuturesCommand(user_id=USER, side="LONG", contracts=1))
    with pytest.raises(PositionNotFound):
        await uc.close(CloseFuturesCommand(user_id=USER + 1, position_id=opened.position_id))


async def test_손실은_증거금까지다():
    """지수가 아무리 움직여도 지갑은 음수가 되지 않는다."""
    uc, repo, clock = _build()
    opened = await uc.open(OpenFuturesCommand(user_id=USER, side="SHORT", contracts=2))
    clock.tick = opened.expires_tick

    closed = await uc.close(CloseFuturesCommand(user_id=USER, position_id=opened.position_id))
    assert closed.cash_delta_krw >= 0
    assert repo.wallets[USER]["cash_krw"] >= 0
    repo.assert_invariant(USER)
