from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime

from stock.app.dtos.forecast_snapshot_dto import (
    CaptureCommand,
    CaptureResult,
    DirectionStat,
    HorizonStat,
    RegimeStat,
    ScoreResult,
    SignalStat,
    SnapshotRow,
    SnapshotScoreUpdate,
    SnapshotSummaryView,
    SummaryKpi,
)
from stock.app.dtos.signal_config_dto import ActiveSignalConfig
from stock.app.dtos.stock_forecast_dto import ForecastQuery
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.ports.input.forecast_snapshot_use_case import ForecastSnapshotUseCase
from stock.app.ports.input.stock_forecast_use_case import StockForecastUseCase
from stock.app.ports.output.forecast_history_port import ForecastHistoryPort
from stock.app.ports.output.forecast_snapshot_repository import ForecastSnapshotRepositoryPort
from stock.app.ports.output.signal_config_port import SignalConfigPort
from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.entities.forecast_snapshot import ForecastSnapshot
from stock.domain.services.indicator_calculator import IndicatorCalculator
from stock.domain.services.outlook_predictor import OutlookPredictor
from stock.domain.value_objects.sentiment_score import SentimentScore

logger = logging.getLogger(__name__)

# 요약 집계에 쓰는 채점분 상한 — 일 ~160건(80종목×2 horizon) 기준 수개월치
SUMMARY_SCORED_CAP = 2000


class ForecastSnapshotInteractor(ForecastSnapshotUseCase):
    """예측 스냅샷 대장 — forecast 재사용(재계산 금지) + 신호 분해를 함께 동결하고 사후 채점한다."""

    def __init__(
        self,
        forecaster: StockForecastUseCase,
        history: ForecastHistoryPort,
        snapshots: ForecastSnapshotRepositoryPort,
        configs: SignalConfigPort | None = None,
    ) -> None:
        # forecaster는 라이브 폴백 없는 조립(market_data=None)이어야 한다 —
        # 스냅샷은 수집 종목의 저장 봉 기준 기록이지 즉석 벤더 호출이 아니다.
        # configs는 forecaster와 **같은 인스턴스**를 주입해야 breakdown과 direction이
        # 같은 조합으로 계산된다(승격 직후 요청이 갈라지는 것 방지).
        self._forecaster = forecaster
        self._history = history
        self._snapshots = snapshots
        self._configs = configs
        self._calculator = IndicatorCalculator()
        self._predictor = OutlookPredictor()

    async def capture(self, command: CaptureCommand) -> CaptureResult:
        active = await self._active_config()  # 실행당 1회 — 전 티커가 같은 조합으로 캡처된다
        entities: list[ForecastSnapshot] = []
        skipped: list[str] = []
        for ticker in dict.fromkeys(t.strip().upper() for t in command.tickers if t.strip()):
            try:
                entities.extend(await self._capture_one(ticker, command.horizons, active))
            except MarketDataUnavailableError:
                skipped.append(ticker)  # 미수집·봉 부족 — 수집이 따라오면 다음 실행에 포함
            except Exception:
                logger.exception("[forecast-snapshot] %s 캡처 실패 — 다음 티커 계속", ticker)
                skipped.append(ticker)
        captured = await self._snapshots.save_many(entities)
        logger.info(
            "[forecast-snapshot] 캡처 %d건(신규 %d) skip %d티커",
            len(entities), captured, len(skipped),
        )
        return CaptureResult(captured=captured, skipped=skipped)

    async def _capture_one(
        self, ticker: str, horizons: list[int], active: ActiveSignalConfig
    ) -> list[ForecastSnapshot]:
        bars = await self._history.find_all_daily_bars(ticker)
        if not bars:
            raise MarketDataUnavailableError(f"수집된 일봉이 없습니다: {ticker}")

        # 신호 분해는 뷰에 없어 여기서 1회 계산 — forecast와 동일 조건(감성 중립·활성 config)
        indicators = self._calculator.compute(
            [b.close for b in bars], [b.low for b in bars],
            [b.high for b in bars], [float(b.volume) for b in bars],
        )
        # 뷰(StockForecastInteractor)와 **같은 조합**이어야 한다 — 갈라지면 저장된 score와
        # direction이 서로 다른 config로 계산된다(감성 중립 경로 전용 활성 조합).
        contributions = self._predictor.breakdown(
            indicators, SentimentScore(value=0.0), active.config
        )
        score = self._predictor.score(contributions)

        out: list[ForecastSnapshot] = []
        for horizon in horizons:
            view = await self._forecaster.forecast(ForecastQuery(symbol=ticker, horizon=horizon))
            prob, band, pos, down = view.probability, view.band, view.position, view.downside
            out.append(ForecastSnapshot(
                ticker=view.resolved_ticker,
                as_of=view.as_of,
                horizon_days=view.horizon_days,
                direction=view.signal_direction,
                base_price=view.base_price,
                score=score,
                signals=tuple(contributions),
                up_rate=prob.up_rate if prob else None,
                sample_size=prob.sample_size if prob else None,
                hits=prob.hits if prob else None,
                ci_low=prob.ci_low if prob else None,
                ci_high=prob.ci_high if prob else None,
                baseline_up_rate=prob.baseline_up_rate if prob else None,
                ready=prob.ready if prob else False,
                band_source=band.source if band else None,
                q25_pct=band.q25_pct if band else None,
                median_pct=band.median_pct if band else None,
                q75_pct=band.q75_pct if band else None,
                regime=view.regime,
                regime_conditional=view.regime_conditional,
                earnings_veto=view.earnings_veto,
                # 어느 조합으로 낸 판정인지 남긴다 — 조합이 바뀌면 이력을 섞어 읽으면 안 된다
                signal_config=active.key,
                rsi=pos.rsi if pos else None,
                bb_percent_b=indicators.bb_percent_b,
                momentum_12_1=indicators.momentum_12_1,
                atr_pct=pos.atr_pct if pos else None,
                drawdown_from_high_pct=pos.drawdown_from_high_pct if pos else None,
                above_support_pct=pos.above_support_pct if pos else None,
                trough_median_pct=down.trough_median_pct if down else None,
                trough_q25_pct=down.trough_q25_pct if down else None,
                recovery_rate=down.recovery_rate if down else None,
                recovery_days_median=down.recovery_days_median if down else None,
            ))
        return out

    async def score(self) -> ScoreResult:
        pending = await self._snapshots.find_pending()
        by_ticker: dict[str, list[ForecastSnapshot]] = defaultdict(list)
        for snap in pending:
            by_ticker[snap.ticker].append(snap)

        now = datetime.now(UTC)
        updates: list[SnapshotScoreUpdate] = []
        for ticker, snaps in by_ticker.items():
            bars = await self._history.find_all_daily_bars(ticker)
            for snap in snaps:
                # 거래일 기준: as_of 이후 horizon번째 봉 종가 = 실현가 (Backtester closes[t+horizon]과 동일)
                future = [b for b in bars if b.ts > snap.as_of]
                if len(future) < snap.horizon_days:
                    continue  # horizon 미도래 — 다음 실행에서 자연 재시도
                realized = future[snap.horizon_days - 1].close
                ret = realized / snap.base_price - 1.0
                # 구간 내 실제 장중 최저 — Backtester의 trough와 같은 정의(저가 기준).
                # 마감가만 남기면 "얼마나 빠졌다 돌아왔는지"를 사후에 물을 수 없다.
                window = future[: snap.horizon_days]
                trough = min(b.low for b in window) / snap.base_price - 1.0
                if snap.direction == "UP":
                    hit = ret > 0
                elif snap.direction == "DOWN":
                    hit = ret <= 0
                else:
                    hit = None
                updates.append(SnapshotScoreUpdate(
                    snapshot_id=snap.id, evaluated_at=now,
                    realized_price=realized, realized_return_pct=ret, hit=hit,
                    realized_trough_pct=trough,
                ))
        scored = await self._snapshots.apply_scores(updates)
        result = ScoreResult(scored=scored, pending=len(pending) - scored)
        logger.info("[forecast-snapshot] 채점 %d건, 대기 %d건", result.scored, result.pending)
        return result

    async def summary(self, horizon: int | None, recent_limit: int) -> SnapshotSummaryView:
        # 현재 활성 조합으로 낸 스냅샷만 집계한다 — 구 조합(NULL 포함)은 규칙이 다른 판정이라
        # 같은 적중률·신호 일치율 분모에 넣으면 서로 다른 성적을 합친 숫자가 된다.
        # 특히 by_signal은 hit이 아니라 실현 수익률 부호로 계산해 구 조합 채점분이 그대로
        # 섞인다. 승격 직후 요약이 0부터 재시작하는 것은 이력 분리의 의도된 동작이다.
        active = await self._active_config()
        total, scored_count = await self._snapshots.counts(horizon, active.key)
        scored = await self._snapshots.find_scored(
            horizon, SUMMARY_SCORED_CAP, active.key
        )
        recent = await self._snapshots.find_recent(horizon, recent_limit, active.key)
        return SnapshotSummaryView(
            kpi=self._kpi(total, scored_count, scored),
            by_horizon=self._by_horizon(scored),
            by_direction=self._by_direction(scored),
            by_regime=self._by_regime(scored),
            by_signal=self._by_signal(scored),
            recent=[self._row(s) for s in recent],
        )

    async def _active_config(self) -> ActiveSignalConfig:
        """활성 판정 조합 — 포트 미주입(구 조립·일부 테스트)이면 코드 상수 폴백."""
        if self._configs is None:
            return ActiveSignalConfig(
                key="forecast_signal", config=AnalysisConfig.forecast_signal()
            )
        return await self._configs.active()

    # ---- 순수 집계 헬퍼 ----

    @staticmethod
    def _hit_rate(snaps: list[ForecastSnapshot]) -> float | None:
        judged = [s for s in snaps if s.hit is not None]
        if not judged:
            return None
        return sum(1 for s in judged if s.hit) / len(judged)

    @staticmethod
    def _avg_return(snaps: list[ForecastSnapshot]) -> float | None:
        rets = [s.realized_return_pct for s in snaps if s.realized_return_pct is not None]
        if not rets:
            return None
        return sum(rets) / len(rets)

    def _kpi(self, total: int, scored_count: int, scored: list[ForecastSnapshot]) -> SummaryKpi:
        ups = [s for s in scored if s.direction == "UP"]
        downs = [s for s in scored if s.direction == "DOWN"]
        return SummaryKpi(
            total=total, scored=scored_count, pending=total - scored_count,
            hit_rate=self._hit_rate(scored),
            up_hit_rate=self._hit_rate(ups),
            down_hit_rate=self._hit_rate(downs),
        )

    def _by_horizon(self, scored: list[ForecastSnapshot]) -> list[HorizonStat]:
        groups: dict[int, list[ForecastSnapshot]] = defaultdict(list)
        for s in scored:
            groups[s.horizon_days].append(s)
        return [
            HorizonStat(
                horizon_days=h, scored=len(g),
                hit_rate=self._hit_rate(g), avg_realized_return_pct=self._avg_return(g),
            )
            for h, g in sorted(groups.items())
        ]

    def _by_direction(self, scored: list[ForecastSnapshot]) -> list[DirectionStat]:
        groups: dict[str, list[ForecastSnapshot]] = defaultdict(list)
        for s in scored:
            groups[s.direction].append(s)
        return [
            DirectionStat(
                direction=d, scored=len(g),
                hit_rate=self._hit_rate(g), avg_realized_return_pct=self._avg_return(g),
            )
            for d, g in sorted(groups.items())
        ]

    def _by_regime(self, scored: list[ForecastSnapshot]) -> list[RegimeStat]:
        groups: dict[str, list[ForecastSnapshot]] = defaultdict(list)
        for s in scored:
            groups[s.regime or "NONE"].append(s)  # 지수 미수집 시기 캡처분은 NONE
        return [
            RegimeStat(
                regime=r, scored=len(g),
                hit_rate=self._hit_rate(g), avg_realized_return_pct=self._avg_return(g),
            )
            for r, g in sorted(groups.items())
        ]

    @staticmethod
    def _by_signal(scored: list[ForecastSnapshot]) -> list[SignalStat]:
        # 신호 부호 ↔ 실현 수익률 부호 일치율. signal==0(무신호)은 표본 제외 —
        # 항상-긍정 편향을 피하고 "신호가 났을 때 맞았는가"만 본다.
        stats: dict[str, tuple[int, int]] = {}
        for s in scored:
            if s.realized_return_pct is None:
                continue
            for c in s.signals:
                if c.signal == 0.0:
                    continue
                n, hits = stats.get(c.key, (0, 0))
                matched = (c.signal > 0) == (s.realized_return_pct > 0)
                stats[c.key] = (n + 1, hits + (1 if matched else 0))
        return [
            SignalStat(key=key, n=n, hits=hits, hit_rate=hits / n if n else None)
            for key, (n, hits) in sorted(stats.items())
        ]

    @staticmethod
    def _row(s: ForecastSnapshot) -> SnapshotRow:
        return SnapshotRow(
            ticker=s.ticker, as_of=s.as_of, horizon_days=s.horizon_days,
            direction=s.direction, base_price=s.base_price, score=s.score,
            up_rate=s.up_rate, ready=s.ready, evaluated_at=s.evaluated_at,
            realized_return_pct=s.realized_return_pct, hit=s.hit,
            regime=s.regime, earnings_veto=s.earnings_veto,
        )
