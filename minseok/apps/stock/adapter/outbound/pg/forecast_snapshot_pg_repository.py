from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from stock.adapter.outbound.orm.forecast_snapshot_orm import ForecastSnapshotOrm
from stock.app.dtos.forecast_snapshot_dto import SnapshotScoreUpdate
from stock.app.ports.output.forecast_snapshot_repository import ForecastSnapshotRepositoryPort
from stock.domain.entities.forecast_snapshot import ForecastSnapshot
from stock.domain.value_objects.signal_breakdown import SignalContribution


class ForecastSnapshotPgRepository(ForecastSnapshotRepositoryPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_many(self, snapshots: list[ForecastSnapshot]) -> int:
        if not snapshots:
            return 0
        stmt = (
            pg_insert(ForecastSnapshotOrm)
            .values([
                {
                    "ticker": s.ticker,
                    "as_of": s.as_of,
                    "horizon_days": s.horizon_days,
                    "direction": s.direction,
                    "base_price": s.base_price,
                    "score": s.score,
                    "signals": [asdict(c) for c in s.signals],
                    "up_rate": s.up_rate,
                    "sample_size": s.sample_size,
                    "hits": s.hits,
                    "ci_low": s.ci_low,
                    "ci_high": s.ci_high,
                    "baseline_up_rate": s.baseline_up_rate,
                    "ready": s.ready,
                    "band_source": s.band_source,
                    "q25_pct": s.q25_pct,
                    "median_pct": s.median_pct,
                    "q75_pct": s.q75_pct,
                    "regime": s.regime,
                    "regime_conditional": s.regime_conditional,
                    "earnings_veto": s.earnings_veto,
                    "signal_config": s.signal_config,
                    "rsi": s.rsi,
                    "bb_percent_b": s.bb_percent_b,
                    "momentum_12_1": s.momentum_12_1,
                    "atr_pct": s.atr_pct,
                    "drawdown_from_high_pct": s.drawdown_from_high_pct,
                    "above_support_pct": s.above_support_pct,
                    "trough_median_pct": s.trough_median_pct,
                    "trough_q25_pct": s.trough_q25_pct,
                    "recovery_rate": s.recovery_rate,
                    "recovery_days_median": s.recovery_days_median,
                }
                for s in snapshots
            ])
            .on_conflict_do_nothing(index_elements=["ticker", "horizon_days", "as_of"])
            .returning(ForecastSnapshotOrm.id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return len(result.scalars().all())

    async def find_pending(self) -> list[ForecastSnapshot]:
        rows = (await self._session.execute(
            select(ForecastSnapshotOrm)
            .where(ForecastSnapshotOrm.evaluated_at.is_(None))
            .order_by(ForecastSnapshotOrm.as_of.asc())
        )).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def apply_scores(self, updates: list[SnapshotScoreUpdate]) -> int:
        if not updates:
            return 0
        for u in updates:
            await self._session.execute(
                update(ForecastSnapshotOrm)
                .where(ForecastSnapshotOrm.id == u.snapshot_id)
                .values(
                    evaluated_at=u.evaluated_at,
                    realized_price=u.realized_price,
                    realized_return_pct=u.realized_return_pct,
                    realized_trough_pct=u.realized_trough_pct,
                    hit=u.hit,
                )
            )
        await self._session.commit()
        return len(updates)

    async def find_scored(
        self, horizon: int | None, limit: int, signal_config: str | None = None
    ) -> list[ForecastSnapshot]:
        stmt = (
            select(ForecastSnapshotOrm)
            .where(ForecastSnapshotOrm.evaluated_at.is_not(None))
            .order_by(ForecastSnapshotOrm.evaluated_at.desc(), ForecastSnapshotOrm.id.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(
            self._narrow(stmt, horizon, signal_config)
        )).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def find_recent(
        self, horizon: int | None, limit: int, signal_config: str | None = None
    ) -> list[ForecastSnapshot]:
        stmt = (
            select(ForecastSnapshotOrm)
            .order_by(ForecastSnapshotOrm.as_of.desc(), ForecastSnapshotOrm.ticker.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(
            self._narrow(stmt, horizon, signal_config)
        )).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def counts(
        self, horizon: int | None, signal_config: str | None = None
    ) -> tuple[int, int]:
        stmt = select(
            func.count(ForecastSnapshotOrm.id),
            func.count(ForecastSnapshotOrm.evaluated_at),
        )
        total, scored = (await self._session.execute(
            self._narrow(stmt, horizon, signal_config)
        )).one()
        return int(total), int(scored)

    @staticmethod
    def _narrow(stmt, horizon: int | None, signal_config: str | None):
        """horizon·판정 조합 좁히기 — 세 조회가 같은 규칙을 쓰게 한 곳에 모은다."""
        if horizon is not None:
            stmt = stmt.where(ForecastSnapshotOrm.horizon_days == horizon)
        if signal_config is not None:
            stmt = stmt.where(ForecastSnapshotOrm.signal_config == signal_config)
        return stmt

    @staticmethod
    def _to_entity(r: ForecastSnapshotOrm) -> ForecastSnapshot:
        return ForecastSnapshot(
            id=r.id, ticker=r.ticker, as_of=r.as_of, horizon_days=r.horizon_days,
            direction=r.direction, base_price=r.base_price, score=r.score,
            signals=tuple(SignalContribution(**c) for c in r.signals),
            up_rate=r.up_rate, sample_size=r.sample_size, hits=r.hits,
            ci_low=r.ci_low, ci_high=r.ci_high, baseline_up_rate=r.baseline_up_rate,
            ready=r.ready, band_source=r.band_source,
            q25_pct=r.q25_pct, median_pct=r.median_pct, q75_pct=r.q75_pct,
            evaluated_at=r.evaluated_at, realized_price=r.realized_price,
            realized_return_pct=r.realized_return_pct,
            realized_trough_pct=r.realized_trough_pct, hit=r.hit,
            regime=r.regime, regime_conditional=r.regime_conditional,
            earnings_veto=r.earnings_veto,
            signal_config=r.signal_config, rsi=r.rsi, bb_percent_b=r.bb_percent_b,
            momentum_12_1=r.momentum_12_1, atr_pct=r.atr_pct,
            drawdown_from_high_pct=r.drawdown_from_high_pct,
            above_support_pct=r.above_support_pct,
            trough_median_pct=r.trough_median_pct, trough_q25_pct=r.trough_q25_pct,
            recovery_rate=r.recovery_rate, recovery_days_median=r.recovery_days_median,
        )
