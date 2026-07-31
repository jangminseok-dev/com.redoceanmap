import pytest

from game.domain.trading.trading_rules import (
    FEE_RATE,
    INITIAL_CASH_KRW,
    RESERVED_CASH_KRW,
    Side,
    close_result,
    entry_cost,
    investable_cash,
    max_quantity,
)


def test_최소_생활자금은_투자에_쓸_수_없다():
    assert investable_cash(INITIAL_CASH_KRW) == INITIAL_CASH_KRW - RESERVED_CASH_KRW
    assert investable_cash(RESERVED_CASH_KRW) == 0
    assert investable_cash(0) == 0


def test_최대_수량은_수수료까지_포함해_예산_안에_든다():
    cash = INITIAL_CASH_KRW
    price = 71_000
    quantity = max_quantity(cash, price)
    assert entry_cost(price, quantity).total_krw <= investable_cash(cash)
    # 한 주 더 사면 예산을 넘어야 한다(최대치가 맞다는 뜻)
    assert entry_cost(price, quantity + 1).total_krw > investable_cash(cash)


def test_예산보다_비싼_종목은_0주다():
    assert max_quantity(150_000, 1_000_000) == 0


def test_진입_수수료는_원금의_요율만큼_붙는다():
    cost = entry_cost(100_000, 10)
    assert cost.principal_krw == 1_000_000
    assert cost.fee_krw == round(1_000_000 * FEE_RATE)
    assert cost.total_krw == cost.principal_krw + cost.fee_krw


# --- 롱 -----------------------------------------------------------------

def test_롱은_오르면_이익_내리면_손실이다():
    entry = entry_cost(10_000, 10)
    gain = close_result(Side.LONG, 10_000, 12_000, 10, 5.0, entry.fee_krw)
    loss = close_result(Side.LONG, 10_000, 8_000, 10, 5.0, entry.fee_krw)
    assert gain.realized_pnl_krw > 0
    assert loss.realized_pnl_krw < 0


def test_롱에는_보유비용이_없다():
    entry = entry_cost(10_000, 10)
    assert close_result(Side.LONG, 10_000, 10_000, 10, 30.0, entry.fee_krw).carry_krw == 0


def test_롱_손실은_투입액을_넘지_않는다():
    """가격이 0에 수렴해도 회수액은 음수가 되지 않는다 — 지갑이 음수가 되면 안 된다."""
    entry = entry_cost(10_000, 10)
    result = close_result(Side.LONG, 10_000, 1, 10, 1.0, entry.fee_krw)
    assert result.proceeds_krw >= 0
    assert result.realized_pnl_krw >= -entry.total_krw


# --- 숏 -----------------------------------------------------------------

def test_숏은_내리면_이익_오르면_손실이다():
    entry = entry_cost(10_000, 10)
    gain = close_result(Side.SHORT, 10_000, 8_000, 10, 1.0, entry.fee_krw)
    loss = close_result(Side.SHORT, 10_000, 12_000, 10, 1.0, entry.fee_krw)
    assert gain.realized_pnl_krw > 0
    assert loss.realized_pnl_krw < 0


def test_숏_손실은_증거금까지다():
    """무한손실이 없어야 지갑이 음수가 되지 않는다. 가격이 10배가 돼도 증거금만 잃는다."""
    entry = entry_cost(10_000, 10)
    result = close_result(Side.SHORT, 10_000, 100_000, 10, 1.0, entry.fee_krw)
    assert result.proceeds_krw == 0
    assert result.realized_pnl_krw == -entry.total_krw


def test_숏_보유비용은_기간에_비례한다():
    entry = entry_cost(10_000, 10)
    short_hold = close_result(Side.SHORT, 10_000, 10_000, 10, 1.0, entry.fee_krw)
    long_hold = close_result(Side.SHORT, 10_000, 10_000, 10, 30.0, entry.fee_krw)
    assert long_hold.carry_krw > short_hold.carry_krw
    assert long_hold.realized_pnl_krw < short_hold.realized_pnl_krw


@pytest.mark.parametrize("side", [Side.LONG, Side.SHORT])
def test_제자리_청산은_수수료만큼_손해다(side):
    """왕복 수수료가 있어야 매 틱 스캘핑이 최적 전략이 되지 않는다."""
    entry = entry_cost(10_000, 10)
    result = close_result(side, 10_000, 10_000, 10, 0.0, entry.fee_krw)
    assert result.realized_pnl_krw < 0
    assert abs(result.realized_pnl_krw) >= entry.fee_krw


@pytest.mark.parametrize("side", [Side.LONG, Side.SHORT])
def test_회수액은_결코_음수가_아니다(side):
    entry = entry_cost(50_000, 3)
    for exit_price in (1, 10, 50_000, 500_000, 5_000_000):
        result = close_result(side, 50_000, exit_price, 3, 100.0, entry.fee_krw)
        assert result.proceeds_krw >= 0
