"""AI 모의투자 대장 — 배치 step(체결 → 청산 판정 → 평가 → 채점 → 판단)과 화면 조회.

시간 규칙: `StepCommand.as_of` 이후의 봉·뉴스·스냅샷은 절대 보지 않는다. 리플레이는 이 함수를
과거 날짜로 순서대로 부르는 것뿐이라 라이브와 같은 코드 경로를 탄다.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

from stock.app.dtos.paper_dto import (
    AccountRecord,
    AccountView,
    BenchmarkPoint,
    BoardRow,
    BoardView,
    DecisionDraft,
    DecisionRecord,
    DecisionView,
    EquityPoint,
    PositionView,
    ScoreBucket,
    ScorecardView,
    ScoreDraft,
    SnapshotFeedRow,
    StepCommand,
    StepResult,
    TradeDraft,
    TradeRecord,
)
from stock.app.ports.input.paper_use_case import PaperUseCase
from stock.app.ports.output.decision_policy_port import DecisionPolicyPort
from stock.app.ports.output.paper_account_repository import PaperAccountRepositoryPort
from stock.app.ports.output.paper_feed_port import PaperFeedPort
from stock.app.ports.output.symbol_directory_port import SymbolDirectoryPort
from stock.domain.services import decision_parser, paper_ledger, paper_rules as rules
from stock.domain.services import signal_rule_policy
from stock.domain.services.decision_context import (
    SYSTEM_PROMPT,
    Candidate,
    DecisionContext,
    HeldView,
    NewsCite,
    build_prompt,
)
from stock.domain.services.decision_parser import Order, reason_kind
from stock.domain.services.decision_scorer import SCORE_HORIZON_SESSIONS, score_entry
from stock.domain.value_objects.backtest_report import wilson_bounds

logger = logging.getLogger(__name__)

HORIZON = 5
NEWS_WINDOW_DAYS = 3
PENDING_EXPIRY_DAYS = 7  # 캘린더일 — 이 안에 체결 봉이 없으면 주문 폐기(휴장 연속 대비)
SCORE_MIN_SAMPLES = 30
MAX_CANDIDATES = 25
LABELS = {"exaone": "EXAONE", "signal": "지표 규칙"}


def _positions_list(account: AccountRecord) -> list[paper_ledger.Position]:
    return list(account.positions)


def _order_dict(o: Order) -> dict:
    return {
        "ticker": o.ticker, "action": o.action, "weight": o.weight, "reason": o.reason,
        "cites": {"news_ids": list(o.news_ids), "signals": list(o.signals)},
        "reason_kind": reason_kind(o),
    }


class PaperInteractor(PaperUseCase):
    def __init__(
        self,
        accounts: PaperAccountRepositoryPort,
        feed: PaperFeedPort,
        policy: DecisionPolicyPort | None,
        directory: SymbolDirectoryPort,
    ) -> None:
        self._accounts = accounts
        self._feed = feed
        self._policy = policy
        self._directory = directory

    # ------------------------------------------------------------------ step
    async def step(self, cmd: StepCommand) -> StepResult:
        as_of = cmd.as_of
        day = as_of.date()
        snapshots = await self._feed.snapshots_on(day, HORIZON)
        if not snapshots:
            return StepResult(as_of, "스냅샷 없음(휴장일)", 0, 0, 0, 0)

        exaone = await self._accounts.get_or_create("exaone", None, rules.assumed_initial_cash_krw, day)
        signal = await self._accounts.get_or_create("signal", None, rules.assumed_initial_cash_krw, day)

        filled = await self._fill_pending(as_of, cmd.replay)
        scored = await self._score_due(as_of)
        equity_rows = await self._record_equity(as_of, cmd.replay)

        decisions = 0
        for account, kind in ((exaone, "exaone"), (signal, "signal")):
            account = await self._accounts.find_by_id(account.id) or account  # 체결 반영분 재조회
            ctx = await self._context(account, snapshots, as_of)
            if kind == "exaone":
                draft = await self._decide_exaone(account, ctx, as_of, cmd.replay)
            else:
                draft = self._decide_signal(account, ctx, as_of, cmd.replay)
            if await self._accounts.save_decision(draft) is not None:
                decisions += 1
        return StepResult(as_of, None, filled, decisions, scored, equity_rows)

    async def _fill_pending(self, as_of: datetime, replay: bool) -> int:
        filled = 0
        for decision in await self._accounts.find_unfilled_decisions():
            if decision.as_of >= as_of:
                continue  # 오늘 낸 판단은 내일 세션에 체결된다
            account = await self._accounts.find_by_id(decision.account_id)
            if account is None:
                continue
            done_tickers = {t.ticker for t in await self._accounts.trades_for_decision(decision.id)}
            cash, positions = account.cash_krw, _positions_list(account)
            prices: dict[str, float] = {}
            pending_left = False
            extra_rejected: list[dict] = []
            for o in decision.orders:
                ticker, action = o["ticker"], o["action"]
                if ticker in done_tickers:
                    continue
                bars = await self._feed.bars_after(ticker, decision.as_of, as_of, 1)
                if not bars:
                    pending_left = True
                    continue
                price = bars[0].open
                prices[ticker] = price
                held = next((p for p in positions if p.ticker == ticker), None)
                if action in ("BUY", "SHORT"):
                    equity = paper_ledger.equity_krw(cash, positions, prices)
                    qty = rules.max_quantity(equity, cash, rules.to_krw(ticker, price), float(o.get("weight") or 0))
                    if qty <= 0:
                        extra_rejected.append({"ticker": ticker, "action": action, "reason": "현금·비중 한도로 1주도 못 산다(보유 종목이 현금을 다 썼을 때가 대부분)"})
                        continue
                else:
                    if held is None:
                        extra_rejected.append({"ticker": ticker, "action": action, "reason": "청산할 포지션이 없다(진입 미체결 또는 이미 청산)"})
                        continue
                    qty = held.quantity
                try:
                    cash, positions, fill = paper_ledger.apply(
                        cash, positions, ticker=ticker, action=action, quantity=qty, price=price, ts=bars[0].ts,
                    )
                except paper_ledger.LedgerError as e:
                    extra_rejected.append({"ticker": ticker, "action": action, "reason": e.reason})
                    continue
                await self._accounts.commit_fill(account.id, cash, positions, TradeDraft(
                    account_id=account.id, ticker=fill.ticker, side=fill.side, action=fill.action,
                    quantity=fill.quantity, price=fill.price, fee_krw=fill.fee_krw,
                    realized_pnl_krw=fill.realized_pnl_krw, ts=fill.ts, decision_id=decision.id,
                    reason=o.get("reason"), evidence=o.get("cites"), replayed=replay,
                ))
                filled += 1
            expired = decision.as_of + timedelta(days=PENDING_EXPIRY_DAYS) <= as_of
            if not pending_left or expired:
                if pending_left:
                    extra_rejected.append({"ticker": "*", "action": "*", "reason": "체결 봉 없이 만료"})
                await self._accounts.mark_filled(decision.id, as_of, extra_rejected)
        return filled

    async def _record_equity(self, as_of: datetime, replay: bool) -> int:
        rows = 0
        for account in await self._accounts.list_accounts():
            prices = {}
            for p in account.positions:
                bars = await self._feed.bars_until(p.ticker, as_of, 1)
                if bars:
                    prices[p.ticker] = bars[-1].close
            positions_value = sum(
                paper_ledger.position_value_krw(p, prices.get(p.ticker, p.avg_price)) for p in account.positions
            )
            point = EquityPoint(
                as_of=as_of.date(), cash_krw=account.cash_krw, positions_value_krw=positions_value,
                equity_krw=account.cash_krw + positions_value, replayed=replay,
            )
            if await self._accounts.upsert_equity(account.id, point):
                rows += 1
        return rows

    async def _score_due(self, as_of: datetime) -> int:
        scored = 0
        for decision in await self._accounts.find_unscored_decisions(as_of):
            fills = {t.ticker: t for t in await self._accounts.trades_for_decision(decision.id)}
            atr_by = {c["ticker"]: c.get("atr_pct") for c in decision.candidates}
            drafts: list[ScoreDraft] = []
            waiting = False
            for o in decision.orders:
                if o["action"] not in ("BUY", "SHORT"):
                    continue
                fill = fills.get(o["ticker"])
                if fill is None:
                    continue  # 미체결(폐기)은 채점 대상이 아니다
                bars = await self._feed.bars_after(o["ticker"], fill.ts, as_of, SCORE_HORIZON_SESSIONS)
                if len(bars) < SCORE_HORIZON_SESSIONS:
                    waiting = True
                    break
                s = score_entry(
                    action=o["action"], reason_kind=o.get("reason_kind", "none"), ticker=o["ticker"],
                    entry_price=fill.price, exit_close=bars[-1].close, atr_pct=atr_by.get(o["ticker"]),
                )
                drafts.append(ScoreDraft(decision.id, s.ticker, s.action, s.reason_kind, s.realized_return_pct, s.hit, as_of))
            if waiting:
                continue
            if drafts:
                scored += await self._accounts.save_scores(drafts)
            await self._accounts.mark_scored(decision.id, as_of)
        return scored

    # ---------------------------------------------------------------- context
    async def _context(self, account: AccountRecord, snapshots: list[SnapshotFeedRow], as_of: datetime) -> DecisionContext:
        since = as_of - timedelta(days=NEWS_WINDOW_DAYS)
        ordered = sorted(snapshots, key=lambda s: (s.direction == "NEUTRAL", -abs(s.score), s.ticker))
        candidates: list[Candidate] = []
        for s in ordered[:MAX_CANDIDATES]:
            bars = await self._feed.bars_until(s.ticker, as_of, 6)
            last = bars[-1].close if bars else s.base_price
            ret5 = (bars[-1].close / bars[0].close - 1.0) if len(bars) >= 6 else None
            news = await self._feed.news_between(s.ticker, since, as_of, 5)
            sentiments = [n.sentiment for n in news if n.sentiment is not None]
            candidates.append(Candidate(
                ticker=s.ticker, name=self._directory.display_name(s.ticker), last_close=last,
                return_5d_pct=ret5, direction=s.direction, score=s.score, up_rate=s.up_rate,
                baseline_up_rate=s.baseline_up_rate, ready=s.ready, atr_pct=s.atr_pct, regime=s.regime,
                earnings_veto=s.earnings_veto,
                sentiment_3d=(sum(sentiments) / len(sentiments)) if sentiments else None,
                news=tuple(NewsCite(n.news_id, n.title, n.sentiment, n.event_type, n.published_at.date(), n.url) for n in news[:2]),
            ))
        held: list[HeldView] = []
        prices: dict[str, float] = {}
        for p in account.positions:
            bars = await self._feed.bars_until(p.ticker, as_of, 1)
            last = bars[-1].close if bars else p.avg_price
            prices[p.ticker] = last
            sessions = len(await self._feed.bars_after(p.ticker, p.opened_at, as_of, 400))
            unreal = (last / p.avg_price - 1.0) if p.side == "LONG" else (p.avg_price / last - 1.0 if last else 0.0)
            held.append(HeldView(p.ticker, p.side, p.quantity, p.avg_price, last, unreal, sessions))
        equity = paper_ledger.equity_krw(account.cash_krw, _positions_list(account), prices)
        return DecisionContext(as_of=as_of.date(), cash_krw=account.cash_krw, equity_krw=equity,
                               candidates=tuple(candidates), held=tuple(held))

    def _candidates_payload(self, ctx: DecisionContext) -> list[dict]:
        return [
            {**{k: v for k, v in asdict(c).items() if k != "news"},
             "news": [asdict(n) | {"published_on": n.published_on.isoformat()} for n in c.news]}
            for c in ctx.candidates
        ]

    async def _decide_exaone(self, account: AccountRecord, ctx: DecisionContext, as_of: datetime, replay: bool) -> DecisionDraft:
        prompt = build_prompt(ctx)
        held_long = {h.ticker for h in ctx.held if h.side == "LONG"}
        held_short = {h.ticker for h in ctx.held if h.side == "SHORT"}
        raw, model, latency = "", "none", 0
        parsed = None
        if self._policy is not None:
            for attempt in range(2):
                try:
                    out = await self._policy.decide(SYSTEM_PROMPT, prompt)
                    raw, model, latency = out.raw, out.model, latency + out.latency_ms
                    parsed = decision_parser.parse(
                        raw, allowed_tickers=ctx.allowed_tickers, allowed_news_ids=ctx.allowed_news_ids,
                        held_long=held_long, held_short=held_short,
                    )
                    break
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning("[paper] EXAONE 응답 파싱 실패(%d/2): %s", attempt + 1, e)
                except Exception as e:  # Ollama 불통 등 — 그날 무거래 기록
                    logger.warning("[paper] EXAONE 호출 실패: %s", e)
                    raw, model = f"(호출 실패) {e}", "unavailable"
                    break
        orders = [_order_dict(o) for o in parsed.orders] if parsed else []
        rejected = [asdict(r) for r in parsed.rejected] if parsed else [{"ticker": "*", "action": "*", "reason": "판단 실패 — 무거래"}]
        return DecisionDraft(
            account_id=account.id, as_of=as_of, model=model, prompt=prompt, response_raw=raw,
            market_view=parsed.market_view if parsed else "(판단 실패)", orders=orders, rejected=rejected,
            candidates=self._candidates_payload(ctx), latency_ms=latency, replayed=replay,
        )

    def _decide_signal(self, account: AccountRecord, ctx: DecisionContext, as_of: datetime, replay: bool) -> DecisionDraft:
        orders = signal_rule_policy.decide(ctx.candidates, ctx.held)
        return DecisionDraft(
            account_id=account.id, as_of=as_of, model="signal-rule", prompt="", response_raw="",
            market_view="검증된 지표 규칙 — 스냅샷 방향 그대로", orders=[_order_dict(o) for o in orders],
            rejected=[], candidates=self._candidates_payload(ctx), latency_ms=0, replayed=replay,
        )

    # ----------------------------------------------------------------- views
    async def board(self) -> BoardView:
        rows: list[BoardRow] = []
        replay_until: date | None = None
        earliest: date | None = None
        for a in await self._accounts.list_accounts():
            series = await self._accounts.equity_series(a.id)
            last = series[-1] if series else None
            equity = last.equity_krw if last else a.cash_krw
            for pt in series:
                if pt.replayed:
                    replay_until = max(replay_until, pt.as_of) if replay_until else pt.as_of
            if series:
                earliest = min(earliest, series[0].as_of) if earliest else series[0].as_of
            rows.append(BoardRow(
                key=a.key, kind=a.kind, label=self._label(a), equity_krw=equity,
                return_pct=equity / a.initial_cash_krw - 1.0, open_positions=len(a.positions),
                trades=await self._accounts.trade_count(a.id), last_as_of=last.as_of if last else None,
            ))
        rows.sort(key=lambda r: -r.return_pct)
        spy: list[BenchmarkPoint] = []
        if earliest:
            bars = [b for b in await self._feed.spy_closes(datetime.now(UTC)) if b.ts.date() >= earliest]
            if bars:
                base = bars[0].close
                spy = [BenchmarkPoint(b.ts.date(), rules.assumed_initial_cash_krw * b.close / base) for b in bars]
        return BoardView(rows=tuple(rows), spy=tuple(spy), replay_until=replay_until, rules=self._rules())

    async def account(self, key: str) -> AccountView | None:
        kind, user_id = self._parse_key(key)
        if kind is None:
            return None
        a = await self._accounts.find(kind, user_id)
        return await self._view(a) if a else None

    async def _view(self, a: AccountRecord) -> AccountView:
        positions: list[PositionView] = []
        prices: dict[str, float] = {}
        for p in a.positions:
            latest = await self._feed.latest_close(p.ticker)
            last = latest[0] if latest else None
            if last is not None:
                prices[p.ticker] = last
            unreal = None
            if last:
                unreal = (last / p.avg_price - 1.0) if p.side == "LONG" else (p.avg_price / last - 1.0)
            positions.append(PositionView(
                ticker=p.ticker, name=self._directory.display_name(p.ticker), side=p.side, quantity=p.quantity,
                avg_price=p.avg_price, last_price=last, unrealized_pct=unreal,
                value_krw=paper_ledger.position_value_krw(p, last if last else p.avg_price), opened_at=p.opened_at,
            ))
        equity = paper_ledger.equity_krw(a.cash_krw, _positions_list(a), prices)
        return AccountView(
            key=a.key, kind=a.kind, label=self._label(a), cash_krw=a.cash_krw, equity_krw=equity,
            initial_cash_krw=a.initial_cash_krw, started_on=a.started_on, positions=tuple(positions),
            equity=tuple(await self._accounts.equity_series(a.id)),
            trades=tuple(await self._accounts.trades(a.id, 200)),
        )

    async def decisions(self, key: str, since: date | None, until: date | None, limit: int) -> list[DecisionView]:
        kind, user_id = self._parse_key(key)
        a = await self._accounts.find(kind, user_id) if kind else None
        if a is None:
            return []
        scores = await self._accounts.scores(a.id)
        by_decision: dict[int, list] = {}
        for s in scores:
            by_decision.setdefault(s.decision_id, []).append(s)
        views = []
        for d in await self._accounts.decisions(a.id, since, until, limit):
            views.append(DecisionView(
                id=d.id, as_of=d.as_of, market_view=d.market_view, orders=d.orders, rejected=d.rejected,
                candidates=d.candidates, fills=tuple(await self._accounts.trades_for_decision(d.id)),
                replayed=d.replayed, latency_ms=d.latency_ms, scores=tuple(by_decision.get(d.id, [])),
            ))
        return views

    async def scorecard(self, key: str) -> ScorecardView | None:
        kind, user_id = self._parse_key(key)
        a = await self._accounts.find(kind, user_id) if kind else None
        if a is None:
            return None
        scores = await self._accounts.scores(a.id)

        def bucket(name: str, items: list) -> ScoreBucket:
            n, hits = len(items), sum(1 for s in items if s.hit)
            if n < SCORE_MIN_SAMPLES:
                return ScoreBucket(name, n, hits, None, None, None)
            lo, hi = wilson_bounds(hits, n)
            return ScoreBucket(name, n, hits, hits / n, lo, hi)

        by_reason = {}
        by_action = {}
        for s in scores:
            by_reason.setdefault(s.reason_kind, []).append(s)
            by_action.setdefault(s.action, []).append(s)
        return ScorecardView(
            total=bucket("total", scores),
            by_reason=tuple(bucket(k, v) for k, v in sorted(by_reason.items())),
            by_action=tuple(bucket(k, v) for k, v in sorted(by_action.items())),
            baseline_up_rate=None, min_samples=SCORE_MIN_SAMPLES,
        )

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _parse_key(key: str) -> tuple[str | None, int | None]:
        return (key, None) if key in ("exaone", "signal") else (None, None)

    @staticmethod
    def _label(a: AccountRecord) -> str:
        return LABELS.get(a.kind, a.kind)

    @staticmethod
    def _rules() -> dict:
        return {
            "rules_version": rules.RULES_VERSION,
            "assumed_initial_cash_krw": rules.assumed_initial_cash_krw,
            "assumed_fee_rate": rules.assumed_fee_rate,
            "assumed_usdkrw": rules.assumed_usdkrw,
            "assumed_max_position_weight": rules.assumed_max_position_weight,
            "assumed_max_positions": rules.assumed_max_positions,
            "assumed_signal_hold_sessions": rules.assumed_signal_hold_sessions,
            "ai_fill": "판단 다음 세션 시가",
        }
