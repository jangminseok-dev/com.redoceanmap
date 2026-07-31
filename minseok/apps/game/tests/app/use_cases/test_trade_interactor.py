import pytest

from game.app.dtos.trade_dto import CloseTradeCommand, OpenTradeCommand
from game.app.exceptions import (
    InsufficientCash,
    InvalidOrder,
    PositionNotFound,
    SeasonClosed,
    UnknownSymbol,
)
from game.app.use_cases.trade_interactor import TradeInteractor
from game.domain.clock.game_epoch import SEASON_TICKS
from game.domain.market import price_engine
from game.domain.market.symbol_params import SYMBOLS
from game.domain.trading.trading_rules import (
    INITIAL_CASH_KRW,
    RESERVED_CASH_KRW,
    max_quantity,
)
from game.tests.app.use_cases.stub_account_repository import StubAccountRepository, StubClock

USER = 7
SYMBOL = SYMBOLS[0].symbol


def _interactor(tick: int = 1_000):
    repo = StubAccountRepository()
    return TradeInteractor(repository=repo, clock=StubClock(tick)), repo


async def test_첫_매매에_계정이_자동_생성되고_초기자본이_원장에_남는다():
    interactor, repo = _interactor()
    await interactor.open(OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=1))

    assert repo.ledger[0]["source"] == "initial"
    assert repo.ledger[0]["amount_krw"] == INITIAL_CASH_KRW
    repo.assert_invariant(USER)


async def test_진입은_현금을_줄이고_원장에_음수로_남는다():
    interactor, repo = _interactor()
    receipt = await interactor.open(
        OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=3)
    )

    assert receipt.cash_delta_krw < 0
    assert receipt.cash_krw == INITIAL_CASH_KRW + receipt.cash_delta_krw
    assert receipt.fee_krw > 0
    repo.assert_invariant(USER)


async def test_체결가는_요청_도착_틱의_가격이다():
    """지연 체결이 없다 — 미래 틱을 조회할 수 없으므로 개념 자체가 성립하지 않는다."""
    interactor, _ = _interactor(tick=2_500)
    receipt = await interactor.open(
        OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=1)
    )
    assert receipt.tick == 2_500
    assert receipt.price_krw == price_engine.price_at(SYMBOLS[0], 2_500)


async def test_청산하면_현금이_돌아오고_불변식이_유지된다():
    interactor, repo = _interactor(tick=1_000)
    opened = await interactor.open(
        OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=2)
    )
    repo.assert_invariant(USER)

    interactor._clock.tick = 1_600  # 게임 10일 경과
    closed = await interactor.close(
        CloseTradeCommand(user_id=USER, position_id=opened.position_id)
    )

    assert closed.cash_delta_krw >= 0
    assert closed.realized_pnl_krw is not None
    repo.assert_invariant(USER)


async def test_왕복_매매_후에도_원장과_지갑이_어긋나지_않는다():
    """돈이 새는지 잡는 것이 원장의 존재 이유다(game-strategy §6-3)."""
    interactor, repo = _interactor(tick=500)
    for i, side in enumerate(("LONG", "SHORT", "LONG")):
        opened = await interactor.open(
            OpenTradeCommand(user_id=USER, symbol=SYMBOLS[i].symbol, side=side, quantity=2)
        )
        interactor._clock.tick += 300
        await interactor.close(CloseTradeCommand(user_id=USER, position_id=opened.position_id))
        repo.assert_invariant(USER)


async def test_잔고는_최소_생활자금_아래로_내려가지_않는다():
    """전 재산을 잃어도 하한이 남는다 — 파산·게임오버가 없다는 규칙의 구현이다."""
    interactor, repo = _interactor(tick=1_000)
    price = price_engine.price_at(SYMBOLS[0], 1_000)
    quantity = max_quantity(INITIAL_CASH_KRW, price)

    opened = await interactor.open(
        OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=quantity)
    )
    # 진입 직후 이미 하한 이상이어야 한다(투자 가능액이 예약분을 뺀 값이므로)
    assert repo.wallets[USER]["cash_krw"] >= RESERVED_CASH_KRW

    interactor._clock.tick = 1_001
    await interactor.close(CloseTradeCommand(user_id=USER, position_id=opened.position_id))
    assert repo.wallets[USER]["cash_krw"] >= RESERVED_CASH_KRW
    repo.assert_invariant(USER)


async def test_투자_가능액을_넘는_주문은_거부한다():
    interactor, repo = _interactor()
    price = price_engine.price_at(SYMBOLS[0], 1_000)
    too_many = max_quantity(INITIAL_CASH_KRW, price) + 1

    with pytest.raises(InsufficientCash):
        await interactor.open(
            OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=too_many)
        )


@pytest.mark.parametrize("quantity", [0, -1, 10_000_000])
async def test_잘못된_수량은_거부한다(quantity):
    interactor, _ = _interactor()
    with pytest.raises(InvalidOrder):
        await interactor.open(
            OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=quantity)
        )


async def test_잘못된_방향은_거부한다():
    interactor, _ = _interactor()
    with pytest.raises(InvalidOrder):
        await interactor.open(
            OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="HOLD", quantity=1)
        )


async def test_없는_종목은_404다():
    interactor, _ = _interactor()
    with pytest.raises(UnknownSymbol):
        await interactor.open(
            OpenTradeCommand(user_id=USER, symbol="005930.KS", side="LONG", quantity=1)
        )


async def test_시즌이_끝나면_새_매매는_막고_청산은_허용한다():
    """청산까지 막으면 마지막 포지션이 영원히 잠긴다."""
    interactor, _ = _interactor(tick=1_000)
    opened = await interactor.open(
        OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=1)
    )

    interactor._clock.tick = SEASON_TICKS + 100
    with pytest.raises(SeasonClosed):
        await interactor.open(
            OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=1)
        )

    closed = await interactor.close(
        CloseTradeCommand(user_id=USER, position_id=opened.position_id)
    )
    assert closed.realized_pnl_krw is not None


async def test_남의_포지션이나_없는_포지션은_거부한다():
    interactor, _ = _interactor()
    await interactor.open(OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=1))

    with pytest.raises(PositionNotFound):
        await interactor.close(CloseTradeCommand(user_id=USER, position_id=999))
    with pytest.raises(PositionNotFound):
        await interactor.close(CloseTradeCommand(user_id=USER + 1, position_id=1))


async def test_같은_포지션을_두_번_청산할_수_없다():
    interactor, repo = _interactor()
    opened = await interactor.open(
        OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=1)
    )
    await interactor.close(CloseTradeCommand(user_id=USER, position_id=opened.position_id))

    with pytest.raises(PositionNotFound):
        await interactor.close(CloseTradeCommand(user_id=USER, position_id=opened.position_id))
    repo.assert_invariant(USER)
