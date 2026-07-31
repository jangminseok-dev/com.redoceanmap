from game.app.dtos.trade_dto import OpenTradeCommand
from game.app.dtos.wallet_dto import WalletQuery
from game.app.use_cases.trade_interactor import TradeInteractor
from game.app.use_cases.wallet_interactor import WalletInteractor
from game.domain.market.symbol_params import SYMBOLS
from game.domain.trading.trading_rules import INITIAL_CASH_KRW, RESERVED_CASH_KRW
from game.tests.app.use_cases.stub_account_repository import StubAccountRepository, StubClock

USER = 3
SYMBOL = SYMBOLS[0].symbol


def _pair(tick: int = 1_000):
    repo = StubAccountRepository()
    clock = StubClock(tick)
    return (
        WalletInteractor(repository=repo, clock=clock),
        TradeInteractor(repository=repo, clock=clock),
        repo,
        clock,
    )


async def test_첫_조회에_초기자본_계정이_만들어진다():
    wallet, _, repo, _ = _pair()
    view = await wallet.get_wallet(WalletQuery(user_id=USER))

    assert view.cash_krw == INITIAL_CASH_KRW
    assert view.total_asset_krw == INITIAL_CASH_KRW
    assert view.total_return_pct == 0.0
    assert view.positions == ()
    repo.assert_invariant(USER)


async def test_투자_가능액은_최소_생활자금을_뺀_값이다():
    wallet, _, _, _ = _pair()
    view = await wallet.get_wallet(WalletQuery(user_id=USER))

    assert view.reserved_krw == RESERVED_CASH_KRW
    assert view.investable_krw == INITIAL_CASH_KRW - RESERVED_CASH_KRW


async def test_보유_포지션이_현재_시세로_평가된다():
    wallet, trade, _, clock = _pair(tick=1_000)
    await trade.open(OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=2))

    clock.tick = 1_300
    view = await wallet.get_wallet(WalletQuery(user_id=USER))

    assert len(view.positions) == 1
    position = view.positions[0]
    assert position.symbol == SYMBOL
    assert position.name == SYMBOLS[0].name
    assert position.current_price_krw > 0
    assert view.position_value_krw == position.market_value_krw
    assert view.total_asset_krw == view.cash_krw + view.position_value_krw


async def test_평가액은_지금_청산하면_돌아올_금액이다():
    """단순 시가평가보다 보수적이다 — 화면 숫자와 실제 회수액이 어긋나지 않게."""
    wallet, trade, _, clock = _pair(tick=1_000)
    receipt = await trade.open(
        OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=5)
    )

    view = await wallet.get_wallet(WalletQuery(user_id=USER))
    position = view.positions[0]
    # 같은 틱에 바로 평가하면 왕복 수수료만큼 마이너스여야 한다
    assert position.unrealized_pnl_krw < 0
    assert position.market_value_krw < receipt.price_krw * 5


async def test_총수익률은_초기자본_대비다():
    wallet, trade, _, _ = _pair()
    await trade.open(OpenTradeCommand(user_id=USER, symbol=SYMBOL, side="LONG", quantity=1))
    view = await wallet.get_wallet(WalletQuery(user_id=USER))

    expected = round((view.total_asset_krw - INITIAL_CASH_KRW) / INITIAL_CASH_KRW * 100, 2)
    assert view.total_return_pct == expected


async def test_조회는_게임_시각을_함께_낸다():
    wallet, _, _, _ = _pair(tick=5_400)
    view = await wallet.get_wallet(WalletQuery(user_id=USER))

    assert view.tick == 5_400
    assert view.game_day == 90
    assert view.game_quarter == 2
    assert view.season_over is False
