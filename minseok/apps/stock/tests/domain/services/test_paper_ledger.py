from datetime import UTC, datetime

import pytest

from stock.domain.services import paper_rules as rules
from stock.domain.services.paper_ledger import LedgerError, Position, apply, equity_krw

TS = datetime(2026, 8, 3, tzinfo=UTC)
FX = rules.assumed_usdkrw


def test_롱_매수_매도_손익과_수수료():
    cash, pos, buy = apply(10_000_000, [], ticker="005930.KS", action="BUY", quantity=10, price=70_000, ts=TS)
    assert buy.fee_krw == 700.0 and cash == 10_000_000 - 700_000 - 700
    assert pos[0] == Position("005930.KS", "LONG", 10, 70_000, TS)
    cash, pos, sell = apply(cash, pos, ticker="005930.KS", action="SELL", quantity=10, price=77_000, ts=TS)
    assert pos == [] and sell.realized_pnl_krw == 70_000 - 770.0
    assert cash == pytest.approx(10_000_000 + 70_000 - 700 - 770)


def test_숏은_담보를_묶고_커버에서_되돌린다():
    cash0 = 1_000_000_000
    cash, pos, _ = apply(cash0, [], ticker="TSLA", action="SHORT", quantity=10, price=100.0, ts=TS)
    notional = 100.0 * 10 * FX
    assert cash == pytest.approx(cash0 - notional - notional * 0.001)
    # 가격 하락 → 숏 이익. 평가액 = (2E − P)q
    assert equity_krw(cash, pos, {"TSLA": 90.0}) == pytest.approx(cash0 - notional * 0.001 + 10 * 10 * FX)
    cash, pos, cover = apply(cash, pos, ticker="TSLA", action="COVER", quantity=10, price=90.0, ts=TS)
    assert pos == [] and cover.realized_pnl_krw == pytest.approx(10 * 10 * FX - 90.0 * 10 * FX * 0.001)
    assert cash == pytest.approx(cash0 + 10 * 10 * FX - notional * 0.001 - 900 * FX * 0.001)


def test_달러_종목은_고정_환율로_원화_환산():
    cash, pos, fill = apply(1_000_000_000, [], ticker="AAPL", action="BUY", quantity=1, price=200.0, ts=TS)
    assert cash == pytest.approx(1_000_000_000 - 200 * FX * 1.001)
    assert fill.fee_krw == pytest.approx(200 * FX * 0.001, abs=0.01)


def test_평가는_현재가_없는_종목을_진입가로_열화():
    pos = [Position("AAPL", "LONG", 2, 100.0, TS)]
    assert equity_krw(0.0, pos, {}) == 200.0 * FX


@pytest.mark.parametrize(
    ("positions", "kwargs", "msg"),
    [
        ([], dict(ticker="AAPL", action="SELL", quantity=1, price=1.0), "포지션이 없습니다"),
        ([Position("AAPL", "LONG", 1, 1.0, TS)], dict(ticker="AAPL", action="SHORT", quantity=1, price=1.0), "반대 포지션"),
        ([Position("AAPL", "LONG", 1, 1.0, TS)], dict(ticker="AAPL", action="SELL", quantity=2, price=1.0), "많이 청산"),
        ([], dict(ticker="AAPL", action="BUY", quantity=1, price=1e9), "현금이 부족"),
        ([], dict(ticker="AAPL", action="BUY", quantity=0, price=1.0), "1주 이상"),
    ],
)
def test_불가능한_주문은_거부한다(positions, kwargs, msg):
    with pytest.raises(LedgerError) as e:
        apply(1_000.0, positions, ts=TS, **kwargs)
    assert msg in e.value.reason


def test_동시_보유_상한():
    positions = [Position(f"T{i}", "LONG", 1, 1.0, TS) for i in range(rules.assumed_max_positions)]
    with pytest.raises(LedgerError):
        apply(1e12, positions, ticker="NEW", action="BUY", quantity=1, price=1.0, ts=TS)
    # 이미 보유한 종목 추가 매수는 상한과 무관
    cash, pos, _ = apply(1e12, positions, ticker="T0", action="BUY", quantity=1, price=3.0, ts=TS)
    assert next(p for p in pos if p.ticker == "T0").avg_price == 2.0


def test_max_quantity_는_비중과_현금_둘_다_지킨다():
    assert rules.max_quantity(100_000_000, 100_000_000, 1_000_000, 0.5) == 19  # 20% 상한 = 2천만 ÷ (100만×1.001)
    assert rules.max_quantity(100_000_000, 500_000, 100_000, 0.2) == 4  # 현금 50만이 먼저 막는다
    assert rules.max_quantity(100_000_000, 100_000_000, 0, 0.2) == 0
