from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.paper_account_orm import PaperAccountOrm, PaperPositionOrm
from stock.adapter.outbound.orm.paper_decision_orm import PaperDecisionOrm, PaperDecisionScoreOrm
from stock.adapter.outbound.orm.paper_equity_daily_orm import PaperEquityDailyOrm
from stock.adapter.outbound.orm.paper_trade_orm import PaperTradeOrm
from stock.app.dtos.paper_dto import (
    AccountRecord, DecisionDraft, DecisionRecord, EquityPoint, ScoreDraft, ScoreRecord, TradeDraft, TradeRecord,
)
from stock.app.ports.output.paper_account_repository import PaperAccountRepositoryPort
from stock.domain.services import paper_rules as rules
from stock.domain.services.paper_ledger import Position


def _trade(r: PaperTradeOrm) -> TradeRecord:
    return TradeRecord(r.id, r.account_id, r.ticker, r.side, r.action, int(r.quantity), r.price, r.fee_krw,
                       r.realized_pnl_krw, r.ts, r.decision_id, r.reason, r.evidence, r.replayed)


def _decision(r: PaperDecisionOrm) -> DecisionRecord:
    return DecisionRecord(r.id, r.account_id, r.as_of, r.model, r.market_view, r.orders, r.rejected, r.candidates,
                          r.latency_ms, r.replayed, r.filled_at, r.scored_at, r.prompt, r.response_raw)


class PaperAccountPgRepository(PaperAccountRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _record(self, row: PaperAccountOrm) -> AccountRecord:
        positions = (await self._session.execute(
            select(PaperPositionOrm).where(PaperPositionOrm.account_id == row.id).order_by(PaperPositionOrm.opened_at)
        )).scalars().all()
        return AccountRecord(
            id=row.id, kind=row.kind, user_id=row.user_id, cash_krw=row.cash_krw,
            initial_cash_krw=row.initial_cash_krw, started_on=row.started_on,
            positions=tuple(Position(p.ticker, p.side, int(p.quantity), p.avg_price, p.opened_at) for p in positions),
        )

    async def get_or_create(self, kind, user_id, initial_cash_krw, started_on):
        found = await self.find(kind, user_id)
        if found:
            return found
        row = PaperAccountOrm(kind=kind, user_id=user_id, cash_krw=initial_cash_krw,
                              initial_cash_krw=initial_cash_krw, started_on=started_on,
                              rules_version=rules.RULES_VERSION)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return await self._record(row)

    async def find(self, kind, user_id):
        stmt = select(PaperAccountOrm).where(PaperAccountOrm.kind == kind)
        stmt = stmt.where(PaperAccountOrm.user_id.is_(None) if user_id is None else PaperAccountOrm.user_id == user_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return await self._record(row) if row else None

    async def find_by_id(self, account_id):
        row = await self._session.get(PaperAccountOrm, account_id)
        return await self._record(row) if row else None

    async def list_accounts(self):
        rows = (await self._session.execute(select(PaperAccountOrm).order_by(PaperAccountOrm.id))).scalars().all()
        return [await self._record(r) for r in rows]

    async def commit_fill(self, account_id, cash_krw, positions, trade):
        # 한 트랜잭션: 현금 갱신 + 포지션 전체 교체 + 원장 1행
        await self._session.execute(update(PaperAccountOrm).where(PaperAccountOrm.id == account_id).values(cash_krw=cash_krw))
        await self._session.execute(delete(PaperPositionOrm).where(PaperPositionOrm.account_id == account_id))
        for p in positions:
            self._session.add(PaperPositionOrm(account_id=account_id, ticker=p.ticker, side=p.side, quantity=p.quantity,
                                               avg_price=p.avg_price, opened_at=p.opened_at))
        row = PaperTradeOrm(**trade.__dict__)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _trade(row)

    async def save_decision(self, draft):
        stmt = insert(PaperDecisionOrm).values(**draft.__dict__).on_conflict_do_nothing(
            constraint="uq_paper_decisions_account_as_of").returning(PaperDecisionOrm.id)
        new_id = (await self._session.execute(stmt)).scalar()
        await self._session.commit()
        if new_id is None:
            return None
        return _decision(await self._session.get(PaperDecisionOrm, new_id))

    async def find_unfilled_decisions(self):
        rows = (await self._session.execute(
            select(PaperDecisionOrm).where(PaperDecisionOrm.filled_at.is_(None)).order_by(PaperDecisionOrm.as_of)
        )).scalars().all()
        return [_decision(r) for r in rows]

    async def mark_filled(self, decision_id, ts, extra_rejected):
        row = await self._session.get(PaperDecisionOrm, decision_id)
        if row is None:
            return
        row.filled_at = ts
        if extra_rejected:
            row.rejected = list(row.rejected or []) + extra_rejected
        await self._session.commit()

    async def find_unscored_decisions(self, before):
        rows = (await self._session.execute(
            select(PaperDecisionOrm).where(
                PaperDecisionOrm.scored_at.is_(None), PaperDecisionOrm.filled_at.is_not(None),
                PaperDecisionOrm.as_of < before,
            ).order_by(PaperDecisionOrm.as_of)
        )).scalars().all()
        return [_decision(r) for r in rows]

    async def mark_scored(self, decision_id, ts):
        await self._session.execute(update(PaperDecisionOrm).where(PaperDecisionOrm.id == decision_id).values(scored_at=ts))
        await self._session.commit()

    async def save_scores(self, scores):
        if not scores:
            return 0
        stmt = insert(PaperDecisionScoreOrm).values([s.__dict__ for s in scores]).on_conflict_do_nothing(
            constraint="uq_paper_decision_scores_decision_ticker")
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or 0

    async def scores(self, account_id):
        rows = (await self._session.execute(
            select(PaperDecisionScoreOrm, PaperDecisionOrm.as_of)
            .join(PaperDecisionOrm, PaperDecisionOrm.id == PaperDecisionScoreOrm.decision_id)
            .where(PaperDecisionOrm.account_id == account_id)
            .order_by(PaperDecisionOrm.as_of)
        )).all()
        return [ScoreRecord(s.decision_id, as_of, s.ticker, s.action, s.reason_kind, s.realized_return_pct, s.hit)
                for s, as_of in rows]

    async def trades_for_decision(self, decision_id):
        rows = (await self._session.execute(
            select(PaperTradeOrm).where(PaperTradeOrm.decision_id == decision_id).order_by(PaperTradeOrm.ts)
        )).scalars().all()
        return [_trade(r) for r in rows]

    async def trades(self, account_id, limit):
        rows = (await self._session.execute(
            select(PaperTradeOrm).where(PaperTradeOrm.account_id == account_id)
            .order_by(PaperTradeOrm.ts.desc()).limit(limit)
        )).scalars().all()
        return [_trade(r) for r in reversed(rows)]

    async def trade_count(self, account_id):
        return int(await self._session.scalar(
            select(func.count()).select_from(PaperTradeOrm).where(PaperTradeOrm.account_id == account_id)) or 0)

    async def upsert_equity(self, account_id, point):
        stmt = insert(PaperEquityDailyOrm).values(account_id=account_id, **point.__dict__).on_conflict_do_nothing(
            constraint="uq_paper_equity_daily_account_as_of")
        result = await self._session.execute(stmt)
        await self._session.commit()
        return bool(result.rowcount)

    async def equity_series(self, account_id):
        rows = (await self._session.execute(
            select(PaperEquityDailyOrm).where(PaperEquityDailyOrm.account_id == account_id).order_by(PaperEquityDailyOrm.as_of)
        )).scalars().all()
        return [EquityPoint(r.as_of, r.cash_krw, r.positions_value_krw, r.equity_krw, r.replayed) for r in rows]

    async def decisions(self, account_id, since, until, limit):
        stmt = select(PaperDecisionOrm).where(PaperDecisionOrm.account_id == account_id)
        if since:
            stmt = stmt.where(func.date(PaperDecisionOrm.as_of) >= since)
        if until:
            stmt = stmt.where(func.date(PaperDecisionOrm.as_of) <= until)
        rows = (await self._session.execute(stmt.order_by(PaperDecisionOrm.as_of.desc()).limit(limit))).scalars().all()
        return [_decision(r) for r in rows]

    async def decision_by_id(self, decision_id):
        row = await self._session.get(PaperDecisionOrm, decision_id)
        return _decision(row) if row else None
