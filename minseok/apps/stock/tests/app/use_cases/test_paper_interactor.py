"""AI 모의투자 대장 — 스텁 포트로 step·주문·조회를 검증한다."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from stock.app.dtos.paper_dto import (
    AccountRecord, DecisionDraft, DecisionRecord, EquityPoint, NewsFeedRow, PlaceOrderCommand,
    ScoreDraft, ScoreRecord, SnapshotFeedRow, StepCommand, TradeDraft, TradeRecord,
)
from stock.app.exceptions import PaperOrderRejected
from stock.app.ports.output.decision_policy_port import PolicyOutput
from stock.app.use_cases.paper_interactor import PaperInteractor
from stock.domain.entities.price_bar import PriceBar
from stock.domain.services import paper_rules as rules

D0 = datetime(2026, 8, 3, 5, 0, tzinfo=UTC)  # 월 14:00 KST


def _day(n: int) -> datetime:
    return D0 + timedelta(days=n)


def _bar(ticker: str, n: int, open_: float, close: float) -> PriceBar:
    # 세션 n의 일봉 — ts는 그날 00:00 UTC(판단 시각 05:00보다 앞) → 판단 다음 세션 봉은 n+1
    return PriceBar(ticker=ticker, timeframe="1d", ts=datetime(2026, 8, 3, tzinfo=UTC) + timedelta(days=n),
                    open=open_, high=max(open_, close), low=min(open_, close), close=close, volume=1)


class StubRepo:
    def __init__(self):
        self.accounts: dict[int, dict] = {}
        self._trades: list[TradeRecord] = []
        self.decisions: dict[int, DecisionRecord] = {}
        self.equity: dict[tuple[int, date], EquityPoint] = {}
        self._scores: list[ScoreRecord] = []
        self._seq = 0

    def _next(self):
        self._seq += 1
        return self._seq

    def _rec(self, a):
        return AccountRecord(a["id"], a["kind"], a["user_id"], a["cash"], a["initial"], a["started"], tuple(a["positions"]))

    async def get_or_create(self, kind, user_id, initial_cash_krw, started_on):
        for a in self.accounts.values():
            if a["kind"] == kind and a["user_id"] == user_id:
                return self._rec(a)
        aid = self._next()
        self.accounts[aid] = dict(id=aid, kind=kind, user_id=user_id, cash=float(initial_cash_krw),
                                  initial=float(initial_cash_krw), started=started_on, positions=[])
        return self._rec(self.accounts[aid])

    async def find(self, kind, user_id):
        return next((self._rec(a) for a in self.accounts.values() if a["kind"] == kind and a["user_id"] == user_id), None)

    async def find_by_id(self, account_id):
        return self._rec(self.accounts[account_id]) if account_id in self.accounts else None

    async def list_accounts(self):
        return [self._rec(a) for a in self.accounts.values()]

    async def commit_fill(self, account_id, cash_krw, positions, trade: TradeDraft):
        self.accounts[account_id]["cash"] = cash_krw
        self.accounts[account_id]["positions"] = list(positions)
        rec = TradeRecord(self._next(), **{k: getattr(trade, k) for k in TradeDraft.__dataclass_fields__})
        self._trades.append(rec)
        return rec

    async def save_decision(self, draft: DecisionDraft):
        if any(d.account_id == draft.account_id and d.as_of == draft.as_of for d in self.decisions.values()):
            return None
        did = self._next()
        rec = DecisionRecord(did, draft.account_id, draft.as_of, draft.model, draft.market_view, draft.orders,
                             draft.rejected, draft.candidates, draft.latency_ms, draft.replayed, None, None,
                             draft.prompt, draft.response_raw)
        self.decisions[did] = rec
        return rec

    async def find_unfilled_decisions(self):
        return [d for d in self.decisions.values() if d.filled_at is None]

    async def mark_filled(self, decision_id, ts, extra_rejected):
        d = self.decisions[decision_id]
        self.decisions[decision_id] = DecisionRecord(**{**d.__dict__, "filled_at": ts, "rejected": d.rejected + extra_rejected})

    async def find_unscored_decisions(self, before):
        return [d for d in self.decisions.values() if d.scored_at is None and d.as_of < before and d.filled_at is not None]

    async def mark_scored(self, decision_id, ts):
        d = self.decisions[decision_id]
        self.decisions[decision_id] = DecisionRecord(**{**d.__dict__, "scored_at": ts})

    async def save_scores(self, scores):
        for s in scores:
            self._scores.append(ScoreRecord(s.decision_id, self.decisions[s.decision_id].as_of, s.ticker, s.action,
                                           s.reason_kind, s.realized_return_pct, s.hit))
        return len(scores)

    async def scores(self, account_id):
        return [s for s in self._scores if self.decisions[s.decision_id].account_id == account_id]

    async def trades_for_decision(self, decision_id):
        return [t for t in self._trades if t.decision_id == decision_id]

    async def trades(self, account_id, limit):
        return [t for t in self._trades if t.account_id == account_id][-limit:]

    async def trade_count(self, account_id):
        return sum(1 for t in self._trades if t.account_id == account_id)

    async def upsert_equity(self, account_id, point):
        key = (account_id, point.as_of)
        if key in self.equity:
            return False
        self.equity[key] = point
        return True

    async def equity_series(self, account_id):
        return sorted((p for (aid, _), p in self.equity.items() if aid == account_id), key=lambda p: p.as_of)

    async def decisions(self, account_id, since, until, limit):
        return sorted((d for d in self.decisions.values() if d.account_id == account_id), key=lambda d: d.as_of, reverse=True)[:limit]

    async def decision_by_id(self, decision_id):
        return self.decisions.get(decision_id)


class StubFeed:
    """세션 n=0..10, AAPL은 매일 +2% 상승, TSLA는 매일 -2% 하락. 스냅샷은 매일 있다."""

    def __init__(self):
        self.bars = {"AAPL": [_bar("AAPL", n, 100 * 1.02 ** n, 100 * 1.02 ** (n + 0.5)) for n in range(12)],
                     "TSLA": [_bar("TSLA", n, 200 * 0.98 ** n, 200 * 0.98 ** (n + 0.5)) for n in range(12)],
                     "SPY": [_bar("SPY", n, 500, 500 + n) for n in range(12)]}
        self.snapshot_days: set[date] = {(_day(n)).date() for n in range(12)}
        self.calls: list[tuple] = []

    async def snapshots_on(self, day, horizon):
        if day not in self.snapshot_days:
            return []
        return [SnapshotFeedRow("AAPL", datetime.combine(day, datetime.min.time(), UTC), "UP", 0.6, 100, 0.6, 0.5, True, 0.02, "BULL", False),
                SnapshotFeedRow("TSLA", datetime.combine(day, datetime.min.time(), UTC), "DOWN", -0.7, 200, 0.6, 0.5, True, 0.03, "BULL", False)]

    async def bars_after(self, ticker, after, until, limit):
        self.calls.append(("bars_after", ticker, after, until))
        return [b for b in self.bars.get(ticker, []) if after < b.ts <= until][:limit]

    async def bars_until(self, ticker, until, limit):
        return [b for b in self.bars.get(ticker, []) if b.ts <= until][-limit:]

    async def latest_close(self, ticker):
        bars = self.bars.get(ticker)
        return (bars[-1].close, bars[-1].ts) if bars else None

    async def news_between(self, ticker, since, until, limit):
        if ticker != "AAPL":
            return []
        return [NewsFeedRow(7, "애플 실적 서프라이즈", "http://x", until - timedelta(hours=3), 0.8, "earnings")]

    async def spy_closes(self, until):
        return [b for b in self.bars["SPY"] if b.ts <= until]


class StubPolicy:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    async def decide(self, system, prompt):
        self.prompts.append(prompt)
        raw = self.responses.pop(0) if self.responses else json.dumps({"market_view": "관망", "orders": []})
        return PolicyOutput(raw=raw, model="stub", latency_ms=10)


class StubDirectory:
    def display_name(self, ticker):
        return {"AAPL": "애플", "TSLA": "테슬라"}.get(ticker, ticker)


def _make(policy=None):
    repo, feed = StubRepo(), StubFeed()
    return PaperInteractor(repo, feed, policy, StubDirectory()), repo, feed


BUY_AAPL = json.dumps({"market_view": "실적 기대", "orders": [
    {"ticker": "AAPL", "action": "BUY", "weight": 0.1, "reason": "실적", "cites": {"news_ids": [7, 99], "signals": ["snapshot_direction"]}},
    {"ticker": "NVDA", "action": "BUY", "weight": 0.1, "reason": "환각"},
]})


async def test_스냅샷_없는_날은_아무것도_하지_않는다():
    it, repo, feed = _make()
    feed.snapshot_days = set()
    result = await it.step(StepCommand(D0))
    assert result.skipped and not repo.decisions and not repo.accounts


async def test_판단은_다음_세션_시가에_체결되고_재실행은_멱등():
    it, repo, feed = _make(StubPolicy([BUY_AAPL]))
    r0 = await it.step(StepCommand(_day(0), replay=True))
    assert r0.decisions == 2 and r0.filled == 0
    exaone = next(d for d in repo.decisions.values() if d.model == "stub")
    assert [o["ticker"] for o in exaone.orders] == ["AAPL"]  # NVDA는 후보 밖 → 거부
    assert exaone.rejected[0]["ticker"] == "NVDA"
    assert exaone.orders[0]["cites"]["news_ids"] == [7]  # 99는 환각 인용 → 제거
    assert exaone.orders[0]["reason_kind"] == "mixed"

    again = await it.step(StepCommand(_day(0), replay=True))
    assert again.decisions == 0 and len(repo.decisions) == 2  # (account, as_of) 유니크

    r1 = await it.step(StepCommand(_day(1)))
    aapl_fills = [t for t in repo._trades if t.ticker == "AAPL" and t.action == "BUY"]
    assert r1.filled >= 1 and aapl_fills
    # 체결가 = 판단 다음 세션(n=1) 시가
    assert aapl_fills[0].price == pytest.approx(feed.bars["AAPL"][1].open)
    assert aapl_fills[0].replayed is False and aapl_fills[0].decision_id == exaone.id
    assert repo.decisions[exaone.id].filled_at is not None
    # 체결 후 평가 행이 계정마다 하루 1건
    assert sum(1 for (aid, d) in repo.equity if d == _day(1).date()) == 2


async def test_피드는_as_of_이후_봉을_주지_않는다():
    """리플레이 정직성 — 체결·평가 조회의 until은 항상 그 step의 as_of다."""
    it, repo, feed = _make(StubPolicy([BUY_AAPL]))
    await it.step(StepCommand(_day(0)))
    await it.step(StepCommand(_day(1)))
    assert all(until <= _day(1) for (_, _, _, until) in feed.calls)


async def test_지표_규칙_계정은_UP_롱_DOWN_숏_그리고_5거래일_뒤_청산():
    it, repo, feed = _make()
    for n in range(8):
        await it.step(StepCommand(_day(n)))
    signal = next(a for a in repo.accounts.values() if a["kind"] == "signal")
    sig_trades = [t for t in repo._trades if t.account_id == signal["id"]]
    actions = [(t.ticker, t.action) for t in sig_trades]
    assert ("AAPL", "BUY") in actions and ("TSLA", "SHORT") in actions
    assert ("AAPL", "SELL") in actions and ("TSLA", "COVER") in actions
    sell = next(t for t in sig_trades if t.action == "SELL")
    buy = next(t for t in sig_trades if t.action == "BUY")
    assert sell.realized_pnl_krw > 0 and sell.ts > buy.ts
    # 숏도 하락장에서 이익
    assert next(t for t in sig_trades if t.action == "COVER").realized_pnl_krw > 0


async def test_진입_판단은_5거래일_뒤_채점된다():
    it, repo, feed = _make(StubPolicy([BUY_AAPL]))
    for n in range(8):
        await it.step(StepCommand(_day(n)))
    exaone = next(a for a in repo.accounts.values() if a["kind"] == "exaone")
    scores = await repo.scores(exaone["id"])
    assert scores and scores[0].ticker == "AAPL" and scores[0].hit is True and scores[0].reason_kind == "mixed"
    card = await it.scorecard("exaone")
    assert card.total.n == 1 and card.total.hit_rate is None  # 표본 30 미만이면 숫자 비노출


async def test_EXAONE_파싱_실패는_무거래로_기록되고_호출은_2회까지():
    it, repo, feed = _make(StubPolicy(["not json", "still not json"]))
    await it.step(StepCommand(_day(0)))
    d = next(d for d in repo.decisions.values() if d.model == "stub")
    assert d.orders == [] and "판단 실패" in d.rejected[0]["reason"]


async def test_사람_주문은_즉시_최신_종가로_체결되고_한도를_지킨다():
    it, repo, feed = _make()
    receipt = await it.place_order(PlaceOrderCommand(user_id=42, ticker="aapl", action="buy", quantity=10))
    assert receipt.ticker == "AAPL" and receipt.price == feed.bars["AAPL"][-1].close
    me = await it.me(42)
    assert me.positions[0].quantity == 10 and me.cash_krw < rules.assumed_initial_cash_krw
    with pytest.raises(PaperOrderRejected):
        await it.place_order(PlaceOrderCommand(42, "AAPL", "BUY", 10_000_000))  # 비중 상한
    with pytest.raises(PaperOrderRejected):
        await it.place_order(PlaceOrderCommand(42, "ZZZZ", "BUY", 1))  # 시세 없음
    with pytest.raises(PaperOrderRejected):
        await it.place_order(PlaceOrderCommand(42, "AAPL", "COVER", 1))  # 숏 없음


async def test_리더보드는_수익률순이고_SPY_기준선을_붙인다():
    it, repo, feed = _make()
    for n in range(3):
        await it.step(StepCommand(_day(n), replay=True))
    board = await it.board()
    assert [r.key for r in board.rows][:2] and board.rows[0].return_pct >= board.rows[-1].return_pct
    assert board.spy and board.spy[0].equity_krw == rules.assumed_initial_cash_krw
    assert board.replay_until == _day(2).date()
    assert board.rules["assumed_fee_rate"] == rules.assumed_fee_rate
