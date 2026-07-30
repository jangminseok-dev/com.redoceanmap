from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from stock.app.dtos.stock_forecast_dto import (
    BandInfo,
    DownsideInfo,
    ForecastQuery,
    ProbabilityInfo,
    StockForecastView,
)
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.ports.input.stock_forecast_use_case import StockForecastUseCase
from stock.app.ports.output.earnings_calendar_port import EarningsCalendarPort
from stock.app.ports.output.forecast_history_port import ForecastHistoryPort
from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.services import forecast_narrator
from stock.domain.services.backtester import Backtester
from stock.domain.services.forecast_narrator import QUANTILE_MIN_SAMPLES
from stock.domain.services.indicator_calculator import IndicatorCalculator
from stock.domain.services.outlook_predictor import OutlookPredictor
from stock.domain.services.regime_calendar import RegimeCalendar
from stock.app.ports.output.market_data_port import MarketDataPort
from stock.domain.value_objects.backtest_report import MIN_SIGNAL_SAMPLES, wilson_bounds
from stock.domain.value_objects.forecast_distribution import ForecastDistribution
from stock.domain.value_objects.market_values import Symbol
from stock.domain.value_objects.position_profile import PositionProfile
from stock.domain.value_objects.sentiment_score import SentimentScore

logger = logging.getLogger(__name__)

SPY_TICKER = "SPY"
VIX_TICKER = "^VIX"
EARNINGS_VETO_DAYS = 2  # 실적 발표 ±N 캘린더일 — 기술지표가 무의미해지는 구간

# 워크포워드가 평가일당 지표를 재계산해 종목당 수 초 걸린다 —
# (티커, horizon)별 최신 봉 기준 1건만 캐시한다(봉은 일 1회 적재라 ts가 바뀌면 자연 무효).
_CACHE: dict[tuple[str, int], tuple[str, StockForecastView]] = {}
# 라이브 모드 전용 — 벤더 2y 다운로드 자체를 막아야 하므로 봉 ts가 아니라 UTC 날짜로
# 신선도를 판단한다(같은 날 재요청이면 다운로드 없이 반환).
_LIVE_CACHE: dict[tuple[str, int], tuple[str, StockForecastView]] = {}
# 레짐 달력 — 지수(SPY·VIX) 일봉으로 전 종목이 공유, 마지막 SPY 봉 ts 기준 1건 캐시.
# SPY가 하루 늦게 적재돼도 다음 봉에서 자연 회복(뷰 _CACHE도 종목 봉 ts 키라 동일 성질).
_REGIME_CACHE: tuple[str, RegimeCalendar] | None = None


class StockForecastInteractor(StockForecastUseCase):
    """확률·예측 밴드 대장 — 저장 일봉을 백테스트 분포로 바꿔 현재 신호에 조건부 매칭한다.

    레짐 조건화: 평가일마다 그 시점 시장 레짐(SPY 200일선·VIX)을 판정해 분포를 국면별로도
    쪼개고, 현재 레짐의 표본이 충분하면(QUANTILE_MIN_SAMPLES 이상) 조건부 통계를 쓴다.
    어닝 veto: 실적 발표 ±2일은 방향을 관망으로 강등하고 백테스트 표본에서도 제외한다
    (벤더가 알려주는 ~12분기 범위 내 — 그 밖의 과거는 제외 못 함).
    """

    def __init__(
        self,
        history: ForecastHistoryPort,
        market_data: MarketDataPort | None = None,
        earnings: EarningsCalendarPort | None = None,
    ) -> None:
        self._history = history
        self._market_data = market_data
        self._earnings = earnings
        self._calculator = IndicatorCalculator()
        self._predictor = OutlookPredictor()
        self._backtester = Backtester(self._calculator, self._predictor)

    async def forecast(self, query: ForecastQuery) -> StockForecastView:
        symbol = query.symbol.strip().upper()
        live = False
        # 캐시 검사는 마지막 봉 1행만 읽어서 — 히트면 수년치 일봉 풀로드를 건너뛴다
        latest = await self._history.find_latest_daily_bar(symbol)
        if latest is None and self._market_data is not None:
            # 미수집 종목 — 다운로드 전에 일 단위 라이브 캐시부터(2y 벤더 호출 자체를 막는다)
            today = datetime.now(UTC).date().isoformat()
            live_cached = _LIVE_CACHE.get((symbol, query.horizon))
            if live_cached is not None and live_cached[0] == today:
                return live_cached[1]
            # 시세 벤더 라이브 이력으로 동일 계산(2y ≈ 500봉, 저장 안 함)
            live_bars = await self._market_data.daily_bars(Symbol(code=symbol))
            latest = live_bars[-1] if live_bars else None
            live = True
        if latest is None:
            raise MarketDataUnavailableError(
                f"수집된 일봉이 없습니다(수집 대상 아님): {query.symbol}"
            )

        cache_key = (latest.ticker, query.horizon)
        last_ts = latest.ts.isoformat()
        cached = _CACHE.get(cache_key)
        if cached is not None and cached[0] == last_ts:
            view = cached[1]
            # 캐시 키는 확정 티커 — 같은 종목을 다른 표기(005930 ↔ 005930.KS)로 물어도
            # 응답 symbol은 이번 요청 표기를 따른다
            return view if view.symbol == symbol else replace(view, symbol=symbol)

        bars = live_bars if live else await self._history.find_all_daily_bars(symbol)
        if not bars:
            raise MarketDataUnavailableError(
                f"수집된 일봉이 없습니다(수집 대상 아님): {query.symbol}"
            )

        closes = [b.close for b in bars]
        lows = [b.low for b in bars]
        highs = [b.high for b in bars]
        volumes = [float(b.volume) for b in bars]
        # 감성 중립 경로 전용 조합 — default()는 감성 가중치 0.5를 전제해 이 경로에서
        # 임계값에 산술적으로 도달하지 못한다(config docstring 참고). 스냅샷 캡처도 같은 것을 쓴다.
        config = AnalysisConfig.forecast_signal()

        calendar = await self._regime_calendar()
        veto_dates = await self._earnings_veto_dates(symbol)

        # 워크포워드는 평가일당 지표 재계산(O(n²)) — 이벤트 루프를 막지 않게 스레드로 분리
        def _compute():
            ind = self._calculator.compute(closes, lows, highs, volumes)
            regimes = (
                [calendar.regime_at(b.ts.date()) for b in bars] if calendar is not None else None
            )
            excluded = (
                [b.ts.date() in veto_dates for b in bars] if veto_dates else None
            )
            return ind, self._backtester.distribution(
                closes, lows, highs, volumes, horizon=query.horizon, config=config,
                regimes=regimes, excluded=excluded,
            )

        try:
            indicators, dist = await asyncio.to_thread(_compute)
        except ValueError as e:  # 봉 부족 — 지표·백테스트 최소 구간 미달
            raise MarketDataUnavailableError(str(e))
        current = self._predictor.predict(indicators, SentimentScore(value=0.0), config)

        direction = current.direction.value
        earnings_veto = bars[-1].ts.date() in veto_dates
        if earnings_veto:
            direction = "NEUTRAL"  # 발표 구간은 방향 주장을 하지 않는다 — 관망 강등

        regime = calendar.regime_at(bars[-1].ts.date()) if calendar is not None else None
        stats, baseline_up_rate, regime_conditional = self._select_stats(dist, direction, regime)

        probability = None
        ready = False
        if stats.sample_size > 0:
            ci_low, ci_high = wilson_bounds(stats.hits, stats.sample_size)
            # 방향별 유의성: UP은 상승 비율이 기준선보다 뚜렷이 높아야, DOWN은 뚜렷이 낮아야
            # (backtest_report의 up/down_probability_ready와 같은 취지). NEUTRAL은 방향 주장이 아니다.
            # 조건부 선택 시 기준선도 같은 레짐 슬라이스의 것 — 국면 자체의 상승률과 비교해야 공정.
            if direction == "UP":
                significant = ci_low > baseline_up_rate
            elif direction == "DOWN":
                significant = ci_high < baseline_up_rate
            else:
                significant = False
            ready = stats.sample_size >= MIN_SIGNAL_SAMPLES and significant
            probability = ProbabilityInfo(
                up_rate=stats.hits / stats.sample_size,
                sample_size=stats.sample_size,
                hits=stats.hits,
                ci_low=ci_low,
                ci_high=ci_high,
                baseline_up_rate=baseline_up_rate,
                ready=ready,
            )

        if stats.sample_size >= QUANTILE_MIN_SAMPLES and stats.median is not None:
            band = BandInfo(
                source="quantile", q25_pct=stats.q25, median_pct=stats.median, q75_pct=stats.q75
            )
        else:
            # 폴백: 변동성(ATR) 기반 대칭 예상 범위 — ±ATR%·√horizon
            move = indicators.atr_pct * (query.horizon ** 0.5)
            band = BandInfo(source="atr", q25_pct=-move, median_pct=0.0, q75_pct=move)

        position = PositionProfile.from_indicators(indicators, closes[-1])
        downside = (
            DownsideInfo(
                trough_median_pct=stats.trough_median_pct,
                trough_q25_pct=stats.trough_q25_pct,
                down_close_rate=stats.down_close_rate,
                dip_samples=stats.dip_samples,
                recovery_rate=stats.recovery_rate,
                recovery_days_median=stats.recovery_days_median,
            )
            if stats.sample_size > 0
            else None
        )

        view = StockForecastView(
            symbol=symbol,
            resolved_ticker=bars[0].ticker,
            as_of=bars[-1].ts,
            base_price=closes[-1],
            horizon_days=query.horizon,
            signal_direction=direction,
            probability=probability,
            band=band,
            insights=forecast_narrator.narrate(
                direction, stats, baseline_up_rate, query.horizon, ready,
                regime=regime, regime_conditional=regime_conditional,
                earnings_veto=earnings_veto,
                position=position,
            ),
            position=position,
            downside=downside,
            live=live,
            regime=regime,
            regime_conditional=regime_conditional,
            earnings_veto=earnings_veto,
        )
        if live:
            _LIVE_CACHE[(symbol, query.horizon)] = (
                datetime.now(UTC).date().isoformat(), view,
            )
        _CACHE[cache_key] = (last_ts, view)
        logger.info(
            "[stock-forecast] %s(%s) %s n=%d evaluated=%d regime=%s cond=%s veto=%s",
            symbol, bars[0].ticker, direction, stats.sample_size, dist.evaluated,
            regime, regime_conditional, earnings_veto,
        )
        return view

    async def _regime_calendar(self) -> RegimeCalendar | None:
        """지수(SPY·VIX) 일봉 → 레짐 달력. 지수 미수집이면 None(무레짐 폴백)."""
        global _REGIME_CACHE
        latest = await self._history.find_latest_daily_bar(SPY_TICKER)
        if latest is None:
            return None
        key = latest.ts.isoformat()
        if _REGIME_CACHE is not None and _REGIME_CACHE[0] == key:
            return _REGIME_CACHE[1]
        spy = await self._history.find_all_daily_bars(SPY_TICKER)
        vix = await self._history.find_all_daily_bars(VIX_TICKER)
        calendar = await asyncio.to_thread(RegimeCalendar.from_bars, spy, vix)
        _REGIME_CACHE = (key, calendar)
        return calendar

    async def _earnings_veto_dates(self, symbol: str) -> set:
        """실적 발표 ±2일 날짜 집합 — 포트 미주입·조회 실패면 빈 집합(무-veto 열화)."""
        if self._earnings is None:
            return set()
        dates = await self._earnings.earnings_dates(symbol)
        return {
            e + timedelta(days=offset)
            for e in dates
            for offset in range(-EARNINGS_VETO_DAYS, EARNINGS_VETO_DAYS + 1)
        }

    @staticmethod
    def _select_stats(dist: ForecastDistribution, direction: str, regime: str | None):
        """현재 레짐 조건부 통계가 충분히 쌓였으면(밴드 기준 표본) 그것을, 아니면 무조건부.

        레짐 분할로 표본이 급감하는 것이 구조적 리스크 — 폴백이 흡수한다.
        ready 게이트(n≥100 + Wilson)는 선택된 슬라이스 위에서 그대로 적용된다.
        """
        if regime is not None and regime in dist.by_regime:
            regime_stats = dist.by_regime[regime]
            conditional = regime_stats.by_direction.get(direction)
            if conditional is not None and conditional.sample_size >= QUANTILE_MIN_SAMPLES:
                return conditional, regime_stats.baseline_up_rate, True
        return dist.by_direction[direction], dist.baseline_up_rate, False
