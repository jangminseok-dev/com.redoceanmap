from datetime import date

from stock.domain.services import paper_rules as rules
from stock.domain.services.decision_context import Candidate, HeldView
from stock.domain.services.signal_rule_policy import ENTRY_WEIGHT, decide


def _c(ticker, direction, score=0.5, veto=False):
    return Candidate(ticker, ticker, 100.0, 0.01, direction, score, 0.55, 0.5, True, 0.02, "BULL", veto, None)


def _h(ticker, side, sessions):
    return HeldView(ticker, side, 1, 100.0, 101.0, 0.01, sessions)


def test_UP은_롱_DOWN은_숏_NEUTRAL은_무시():
    orders = decide((_c("A", "UP"), _c("B", "DOWN"), _c("C", "NEUTRAL")), ())
    assert [(o.ticker, o.action, o.weight) for o in orders] == [("A", "BUY", ENTRY_WEIGHT), ("B", "SHORT", ENTRY_WEIGHT)]
    assert all(o.signals == ("snapshot_direction",) for o in orders)


def test_실적_임박과_보유_종목은_진입하지_않는다():
    orders = decide((_c("A", "UP", veto=True), _c("B", "UP")), (_h("B", "LONG", 1),))
    assert orders == ()


def test_보유_만료와_반대_신호는_청산():
    orders = decide((_c("A", "DOWN"), _c("B", "NEUTRAL")), (_h("A", "LONG", 1), _h("B", "SHORT", rules.assumed_signal_hold_sessions)))
    assert [(o.ticker, o.action) for o in orders] == [("A", "SELL"), ("B", "COVER")]
    assert "반대 신호" in orders[0].reason and "만료" in orders[1].reason


def test_빈_슬롯만큼만_신호가_뚜렷한_순으로_진입():
    held = tuple(_h(f"H{i}", "LONG", 1) for i in range(rules.assumed_max_positions - 1))
    cands = (_c("WEAK", "UP", 0.36), _c("STRONG", "DOWN", -0.9))
    orders = decide(cands, held)
    assert [o.ticker for o in orders] == ["STRONG"]
