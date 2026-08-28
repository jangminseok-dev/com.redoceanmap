from __future__ import annotations

from dataclasses import dataclass

from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.entities.outlook import Direction
from stock.domain.services.indicator_calculator import MA_LONG, IndicatorCalculator
from stock.domain.services.outlook_predictor import OutlookPredictor
from stock.domain.value_objects.backtest_report import (
    BacktestReport,
    hit_unit,
    is_down_hit,
    is_up_hit,
)
from stock.domain.value_objects.forecast_distribution import (
    DirectionStats,
    ForecastDistribution,
    RegimeStats,
)
from stock.domain.value_objects.sentiment_score import SentimentScore

DEFAULT_HORIZON_DAYS = 5


class Backtester:
    """과거 일봉으로 방향 전망의 적중률을 채점하는 순수 도메인 서비스.

    워크포워드: 각 평가일 t에서 t까지의 데이터로만 지표를 계산해 전망을 내고,
    t+horizon 종가와 비교한다(미래 참조 없음). 과거 뉴스는 수집할 수 없으므로
    감성은 중립(0.0) 고정 — 지표 신호만 평가한다.

    적중은 수익률 부호가 아니라 **변동성 대비 초과분**이다(`is_up_hit`) — 기준선도
    같은 규칙으로 세어야 비교가 성립하므로 baseline_up_rate도 함께 바뀐다.
    """

    def __init__(
        self,
        calculator: IndicatorCalculator | None = None,
        predictor: OutlookPredictor | None = None,
    ) -> None:
        self._calculator = calculator or IndicatorCalculator()
        self._predictor = predictor or OutlookPredictor()

    def run(
        self,
        closes: list[float],
        lows: list[float],
        highs: list[float],
        volumes: list[float] | None = None,
        *,
        horizon: int = DEFAULT_HORIZON_DAYS,
        config: AnalysisConfig | None = None,
    ) -> BacktestReport:
        return self.sweep(
            closes, lows, highs, volumes,
            horizon=horizon, configs=[config or AnalysisConfig.default()],
        )[0]

    def sweep(
        self,
        closes: list[float],
        lows: list[float],
        highs: list[float],
        volumes: list[float] | None = None,
        *,
        horizon: int = DEFAULT_HORIZON_DAYS,
        configs: list[AnalysisConfig],
    ) -> list[BacktestReport]:
        """여러 config를 한 번에 채점 — 지표는 평가일당 1회만 계산(스윕 비용 절감)."""
        neutral = SentimentScore(value=0.0)
        start = MA_LONG + 1  # 지표 계산 최소 데이터
        end = len(closes) - horizon
        if end <= start:
            raise ValueError(
                f"백테스트에는 최소 {start + horizon + 1}개 봉이 필요합니다 (현재 {len(closes)}개)."
            )

        evaluated = end - start
        indicator_outcomes = []
        baseline_up = baseline_down = 0
        for t in range(start, end):
            indicators = self._calculator.compute(
                closes[: t + 1],
                lows[: t + 1],
                highs[: t + 1],
                volumes[: t + 1] if volumes is not None else None,
            )
            ret = closes[t + horizon] / closes[t] - 1.0
            unit = hit_unit(indicators.atr_pct, horizon)
            baseline_up += 1 if is_up_hit(ret, unit) else 0
            baseline_down += 1 if is_down_hit(ret, unit) else 0
            indicator_outcomes.append((indicators, ret, unit))

        reports = []
        for config in configs:
            up = down = neutral_count = up_hits = down_hits = 0
            for indicators, ret, unit in indicator_outcomes:
                outlook = self._predictor.predict(indicators, neutral, config)
                if outlook.direction is Direction.UP:
                    up += 1
                    up_hits += 1 if is_up_hit(ret, unit) else 0
                elif outlook.direction is Direction.DOWN:
                    down += 1
                    down_hits += 1 if is_down_hit(ret, unit) else 0
                else:
                    neutral_count += 1
            reports.append(BacktestReport(
                horizon_days=horizon,
                evaluated=evaluated,
                up_signals=up,
                down_signals=down,
                neutral_signals=neutral_count,
                up_hits=up_hits,
                down_hits=down_hits,
                baseline_up_rate=baseline_up / evaluated,
                baseline_down_rate=baseline_down / evaluated,
            ))
        return reports

    def distribution(
        self,
        closes: list[float],
        lows: list[float],
        highs: list[float],
        volumes: list[float] | None = None,
        *,
        horizon: int = DEFAULT_HORIZON_DAYS,
        config: AnalysisConfig | None = None,
        regimes: list[str | None] | None = None,
        excluded: list[bool] | None = None,
    ) -> ForecastDistribution:
        """run()과 같은 워크포워드로 방향별 실현 수익률 분포를 수집한다.

        적중 카운트(BacktestReport)가 아니라 수익률 원분포(분위수)가 필요할 때 쓴다 —
        확률·예측 밴드의 재료. 감성은 중립 고정(지표 신호 기준).

        regimes/excluded는 봉 배열과 같은 길이·정렬(호출부가 날짜→값 매핑을 끝내서 주입 —
        도메인은 날짜를 모른다). excluded[t]=True인 평가일(어닝 ±2일 등)은 전 통계에서
        제외하고 vetoed로 센다. regimes[t]가 있으면 무조건부와 별개로 레짐 슬라이스에도
        누적한다(None은 무조건부에만 — 지수 데이터 미형성 구간).
        """
        cfg = config or AnalysisConfig.default()
        neutral = SentimentScore(value=0.0)
        start = MA_LONG + 1
        end = len(closes) - horizon
        if end <= start:
            raise ValueError(
                f"백테스트에는 최소 {start + horizon + 1}개 봉이 필요합니다 (현재 {len(closes)}개)."
            )
        if regimes is not None and len(regimes) != len(closes):
            raise ValueError(f"regimes 길이가 봉 수와 다릅니다: {len(regimes)} != {len(closes)}")
        if excluded is not None and len(excluded) != len(closes):
            raise ValueError(f"excluded 길이가 봉 수와 다릅니다: {len(excluded)} != {len(closes)}")

        outcomes: dict[str, list[_Outcome]] = {d.value: [] for d in Direction}
        regime_outcomes: dict[str, dict[str, list[_Outcome]]] = {}
        regime_baseline_up: dict[str, int] = {}
        regime_baseline_down: dict[str, int] = {}
        baseline_up = baseline_down = 0
        vetoed = 0
        for t in range(start, end):
            if excluded is not None and excluded[t]:
                vetoed += 1
                continue
            indicators = self._calculator.compute(
                closes[: t + 1],
                lows[: t + 1],
                highs[: t + 1],
                volumes[: t + 1] if volumes is not None else None,
            )
            base = closes[t]
            ret = closes[t + horizon] / base - 1.0
            unit = hit_unit(indicators.atr_pct, horizon)
            # 구간 내 하방·회복 — 마감 수익률만으로는 "빠졌다 회복한 것"과 "그냥 오른 것"이 구분되지
            # 않는다. 낙폭은 장중 저가, 회복은 종가 기준(기준가를 실제로 되찾은 날).
            trough = min(lows[t + 1 : t + horizon + 1]) / base - 1.0
            recovery_day = next(
                (k for k, c in enumerate(closes[t + 1 : t + horizon + 1], start=1) if c >= base),
                None,
            )
            baseline_up += 1 if is_up_hit(ret, unit) else 0
            baseline_down += 1 if is_down_hit(ret, unit) else 0
            outlook = self._predictor.predict(indicators, neutral, cfg)
            outcome = _Outcome(ret=ret, unit=unit, trough=trough, recovery_day=recovery_day)
            outcomes[outlook.direction.value].append(outcome)
            regime = regimes[t] if regimes is not None else None
            if regime is not None:
                bucket = regime_outcomes.setdefault(regime, {d.value: [] for d in Direction})
                bucket[outlook.direction.value].append(outcome)
                regime_baseline_up[regime] = (
                    regime_baseline_up.get(regime, 0) + (1 if is_up_hit(ret, unit) else 0)
                )
                regime_baseline_down[regime] = (
                    regime_baseline_down.get(regime, 0) + (1 if is_down_hit(ret, unit) else 0)
                )

        evaluated = end - start - vetoed
        if evaluated <= 0:
            raise ValueError("전 평가일이 제외(veto)되어 분포를 만들 수 없습니다.")
        return ForecastDistribution(
            horizon_days=horizon,
            evaluated=evaluated,
            baseline_up_rate=baseline_up / evaluated,
            baseline_down_rate=baseline_down / evaluated,
            by_direction=_direction_stats(outcomes),
            by_regime={
                regime: RegimeStats(
                    evaluated=(n := sum(len(rows) for rows in bucket.values())),
                    baseline_up_rate=regime_baseline_up.get(regime, 0) / n,
                    baseline_down_rate=regime_baseline_down.get(regime, 0) / n,
                    by_direction=_direction_stats(bucket),
                )
                for regime, bucket in regime_outcomes.items()
            },
            vetoed=vetoed,
        )


@dataclass(frozen=True, slots=True)
class _Outcome:
    """평가일 1건의 사후 결과 — 마감 수익률 + 구간 내 최대 낙폭 + 기준가 회복일."""

    ret: float
    unit: float               # 그날의 변동성 1단위(ATR% × √horizon) — 적중 판정 분모
    trough: float             # 장중 저가 기준 최대 낙폭 (0 이상이면 구간 내 하락 없음)
    recovery_day: int | None  # 기준가를 종가로 되찾은 첫 거래일(1-based), 못 찾으면 None


def _direction_stats(outcomes: dict[str, list[_Outcome]]) -> dict[str, DirectionStats]:
    return {direction: _stats_of(rows) for direction, rows in outcomes.items()}


def _stats_of(rows: list[_Outcome]) -> DirectionStats:
    rets = [o.ret for o in rows]
    troughs = [o.trough for o in rows]
    # 회복률의 분모는 "실제로 빠진 적이 있는" 표본뿐 — 무조정 상승일을 섞으면 회복률이 부풀려진다.
    dips = [o for o in rows if o.trough < 0]
    recovered = [o.recovery_day for o in dips if o.recovery_day is not None]
    return DirectionStats(
        sample_size=len(rows),
        hits=sum(1 for o in rows if is_up_hit(o.ret, o.unit)),
        down_hits=sum(1 for o in rows if is_down_hit(o.ret, o.unit)),
        q25=_quantile(rets, 0.25),
        median=_quantile(rets, 0.5),
        q75=_quantile(rets, 0.75),
        trough_median_pct=_quantile(troughs, 0.5),
        trough_q25_pct=_quantile(troughs, 0.25),
        down_close_rate=(sum(1 for r in rets if r < 0) / len(rets)) if rets else None,
        dip_samples=len(dips),
        recovery_rate=(len(recovered) / len(dips)) if dips else None,
        recovery_days_median=_quantile([float(d) for d in recovered], 0.5),
    )


def _quantile(values: list[float], q: float) -> float | None:
    """선형 보간 분위수 — 표본 2개 미만이면 None(밴드 산출 불가)."""
    if len(values) < 2:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)
