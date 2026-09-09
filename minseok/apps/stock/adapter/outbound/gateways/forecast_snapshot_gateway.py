from __future__ import annotations

from hub.app.dtos.forecast_snapshot_dto import (
    AccuracyKpi,
    DirectionStat,
    ForecastAccuracyReport,
    ForecastCaptureOutcome,
    ForecastScoreOutcome,
    HorizonStat,
    RegimeStat,
    SignalStat,
    SnapshotInfo,
)
from hub.app.ports.output.forecast_snapshot_port import ForecastSnapshotPort
from stock.app.dtos.forecast_snapshot_dto import CaptureCommand
from stock.app.ports.input.forecast_snapshot_use_case import ForecastSnapshotUseCase


class ForecastSnapshotGateway(ForecastSnapshotPort):
    """허브 ForecastSnapshotPort 구현 — app DTO를 허브 계약 DTO로 변환해 위임."""

    def __init__(self, use_case: ForecastSnapshotUseCase) -> None:
        self._use_case = use_case

    async def capture(self, tickers: list[str], horizons: list[int]) -> ForecastCaptureOutcome:
        result = await self._use_case.capture(CaptureCommand(tickers=tickers, horizons=horizons))
        return ForecastCaptureOutcome(
            captured=result.captured, skipped=result.skipped, as_of=result.as_of,
        )

    async def score(self) -> ForecastScoreOutcome:
        result = await self._use_case.score()
        return ForecastScoreOutcome(scored=result.scored, pending=result.pending)

    async def accuracy_report(self, horizon: int | None, recent_limit: int) -> ForecastAccuracyReport:
        view = await self._use_case.summary(horizon=horizon, recent_limit=recent_limit)
        return ForecastAccuracyReport(
            kpi=AccuracyKpi(
                total=view.kpi.total, scored=view.kpi.scored, pending=view.kpi.pending,
                hit_rate=view.kpi.hit_rate, up_hit_rate=view.kpi.up_hit_rate,
                down_hit_rate=view.kpi.down_hit_rate,
            ),
            by_horizon=[
                HorizonStat(
                    horizon_days=h.horizon_days, scored=h.scored,
                    hit_rate=h.hit_rate, avg_realized_return_pct=h.avg_realized_return_pct,
                )
                for h in view.by_horizon
            ],
            by_direction=[
                DirectionStat(
                    direction=d.direction, scored=d.scored,
                    hit_rate=d.hit_rate, avg_realized_return_pct=d.avg_realized_return_pct,
                )
                for d in view.by_direction
            ],
            by_regime=[
                RegimeStat(
                    regime=r.regime, scored=r.scored,
                    hit_rate=r.hit_rate, avg_realized_return_pct=r.avg_realized_return_pct,
                )
                for r in view.by_regime
            ],
            by_signal=[
                SignalStat(key=s.key, n=s.n, hits=s.hits, hit_rate=s.hit_rate)
                for s in view.by_signal
            ],
            recent=[
                SnapshotInfo(
                    ticker=r.ticker, as_of=r.as_of, horizon_days=r.horizon_days,
                    direction=r.direction, base_price=r.base_price, score=r.score,
                    up_rate=r.up_rate, ready=r.ready, evaluated_at=r.evaluated_at,
                    realized_return_pct=r.realized_return_pct, hit=r.hit,
                    regime=r.regime, earnings_veto=r.earnings_veto,
                )
                for r in view.recent
            ],
        )
