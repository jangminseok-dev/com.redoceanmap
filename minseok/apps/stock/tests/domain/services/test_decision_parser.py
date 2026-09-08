import json

import pytest

from stock.domain.services import paper_rules as rules
from stock.domain.services.decision_parser import Order, parse, reason_kind

ALLOWED = {"AAPL", "TSLA", "005930.KS"}
NEWS = {1, 2, 3}


def _parse(payload, **kw):
    base = dict(allowed_tickers=ALLOWED, allowed_news_ids=NEWS, held_long=set(), held_short=set())
    base.update(kw)
    return parse(json.dumps(payload, ensure_ascii=False), **base)


def test_정상_주문과_인용을_통과시킨다():
    out = _parse({"market_view": "완만한 강세", "orders": [
        {"ticker": "aapl", "action": "buy", "weight": 0.1, "reason": "실적 기대", "cites": {"news_ids": [1, 99], "signals": ["snapshot_direction", 5]}},
    ]})
    assert out.market_view == "완만한 강세" and not out.rejected
    o = out.orders[0]
    assert o.ticker == "AAPL" and o.action == "BUY" and o.weight == 0.1
    assert o.news_ids == (1,)  # 99는 제시하지 않은 id — 환각 인용 차단
    assert o.signals == ("snapshot_direction",)


def test_코드펜스로_감싼_JSON도_읽는다():
    raw = '```json\n{"market_view": "", "orders": []}\n```'
    out = parse(raw, allowed_tickers=ALLOWED, allowed_news_ids=NEWS, held_long=set(), held_short=set())
    assert out.orders == ()


def test_깨진_JSON은_ValueError():
    with pytest.raises(ValueError):
        parse("오늘은 관망", allowed_tickers=ALLOWED, allowed_news_ids=NEWS, held_long=set(), held_short=set())


@pytest.mark.parametrize(
    ("order", "held_long", "held_short", "msg"),
    [
        ({"ticker": "NVDA", "action": "BUY", "weight": 0.1}, set(), set(), "후보 목록에 없는"),
        ({"ticker": "AAPL", "action": "HOLD"}, set(), set(), "알 수 없는 주문"),
        ({"ticker": "AAPL", "action": "SELL"}, set(), set(), "보유하지 않은 롱"),
        ({"ticker": "AAPL", "action": "COVER"}, set(), set(), "보유하지 않은 숏"),
        ({"ticker": "AAPL", "action": "SHORT", "weight": 0.1}, {"AAPL"}, set(), "반대 포지션"),
        ({"ticker": "AAPL", "action": "BUY", "weight": 0}, set(), set(), "비중이 0"),
    ],
)
def test_위반_주문은_사유와_함께_거부(order, held_long, held_short, msg):
    out = _parse({"orders": [order]}, held_long=held_long, held_short=held_short)
    assert out.orders == () and msg in out.rejected[0].reason


def test_비중_상한을_넘기면_잘라내고_청산은_0():
    out = _parse({"orders": [
        {"ticker": "AAPL", "action": "BUY", "weight": 0.9},
        {"ticker": "TSLA", "action": "SELL", "weight": 0.5},
    ]}, held_long={"TSLA"})
    assert out.orders[0].weight == rules.assumed_max_position_weight
    assert out.orders[1].weight == 0.0


def test_중복_주문은_한_번만():
    out = _parse({"orders": [{"ticker": "AAPL", "action": "BUY", "weight": 0.1}] * 2})
    assert len(out.orders) == 1 and "중복" in out.rejected[0].reason


def test_이유_유형_분류():
    assert reason_kind(Order("A", "BUY", 0.1, "", (1,), ("x",))) == "mixed"
    assert reason_kind(Order("A", "BUY", 0.1, "", (1,), ())) == "news"
    assert reason_kind(Order("A", "BUY", 0.1, "", (), ("x",))) == "indicator"
    assert reason_kind(Order("A", "BUY", 0.1, "", (), ())) == "none"
