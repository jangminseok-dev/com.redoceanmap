from __future__ import annotations

from core import chart_pattern
from game.app.dtos.market_price_dto import (
    CandleView,
    ChartPatternView,
    MarketEventView,
    MarketPricesResponse,
    MarketPriceQuery,
    PricePoint,
    SymbolInfo,
    SymbolPrices,
)
from game.app.exceptions import InvalidTickRange, UnknownSymbol
from game.app.ports.input.market_price_use_case import MarketPriceUseCase
from game.app.ports.output.game_clock_port import GameClockPort
from game.app.ports.output.game_intervention_repository import GameInterventionRepository
from game.app.use_cases.active_interventions import load_active
from game.domain.clock.game_epoch import (
    GAME_EPOCH_ID,
    RULES_VERSION,
    SEASON_TICKS,
    TICKS_PER_GAME_DAY,
    describe,
)
from game.domain.market import market_events, price_engine
from game.domain.market.symbol_params import (
    CALIBRATED_AT,
    MEME_SIGMA_MULTIPLIER,
    SIGMA_GAME_MULTIPLIER,
    SYMBOLS,
)

MIN_TICKS = 2
MAX_TICKS = 240  # 12종목 × 240틱이 응답 목표(p95 200ms) 안에 드는 상한
MIN_CANDLE_DAYS = 1
MAX_CANDLE_DAYS = 14  # 하루당 60회 평가(≈2.7ms) — 14일이 응답 목표 안에 드는 상한
MIN_PATTERN_POINTS = 60  # 이보다 짧으면 극값이 형태를 이루지 못한다(게임 1일)
MAX_PATTERNS = 3         # 신뢰도 상위만. 전부 그리면 차트가 선으로 덮인다


class MarketPriceInteractor(MarketPriceUseCase):
    """게임 시세 대장 — 현재 틱을 받아 전 종목 곡선을 계산한다.

    가격을 저장하지도, 캐시하지도 않는다. 계산이 정본이다(game-harness §4-2).
    """

    def __init__(
        self,
        clock: GameClockPort,
        interventions: GameInterventionRepository | None = None,
    ) -> None:
        self._clock = clock
        self._interventions = interventions

    async def list_prices(self, query: MarketPriceQuery) -> MarketPricesResponse:
        if not MIN_TICKS <= query.ticks <= MAX_TICKS:
            raise InvalidTickRange(f"ticks는 {MIN_TICKS}~{MAX_TICKS} 범위여야 합니다")

        # 현재 틱까지만 계산한다 — 미래 틱은 만들지 않는다(§1-6).
        # 시즌이 끝났으면 마지막 틱에 멈춘다(그 뒤로는 가격이 변하지 않는다).
        now_tick = self._clock.now_tick()
        moment = describe(now_tick)
        end_tick = min(now_tick, SEASON_TICKS)
        # 관리자 개입 — 아래 모든 가격·뉴스가 같은 목록을 본다
        extra = await load_active(self._interventions, end_tick)

        symbols = tuple(
            SymbolPrices(
                symbol=params.symbol,
                name=params.name,
                sector=params.sector,
                sector_group=params.sector_group,
                meme=params.meme,
                price_krw=price_engine.price_at(params, end_tick, None, extra),
                change_pct=round(
                    price_engine.change_pct(params, end_tick, TICKS_PER_GAME_DAY, extra), 2
                ),
                series=tuple(
                    PricePoint(tick=t, price_krw=p)
                    for t, p in price_engine.price_series(
                        params, end_tick, query.ticks, extra
                    )
                ),
            )
            for params in SYMBOLS
        )
        candles, symbol_info = self._candles_for(query, end_tick, extra)
        patterns = self._patterns_for(query, symbols)
        return MarketPricesResponse(
            events=tuple(
                MarketEventView(
                    tick=e.tick,
                    scope=e.scope,
                    target=e.target,
                    target_name=e.target_name,
                    positive=e.positive,
                    headline=e.headline,
                    affected_symbols=market_events.affected_symbols(e),
                    expected_impact_pct=round(e.shock * 100.0, 2),
                    remaining_impact_pct=round(
                        market_events.event_contribution(e, end_tick) * 100.0, 2
                    ),
                )
                for e in market_events.recent_headlines(end_tick, extra=extra)
            ),
            virtual=True,
            calibrated=CALIBRATED_AT is not None,
            epoch_id=GAME_EPOCH_ID,
            rule_version=RULES_VERSION,
            tick=moment.tick,
            game_day=moment.game_day,
            game_quarter=moment.game_quarter,
            season_over=moment.season_over,
            symbols=symbols,
            candles=candles,
            symbol_info=symbol_info,
            patterns=patterns,
        )

    def _patterns_for(
        self, query: MarketPriceQuery, symbols: tuple[SymbolPrices, ...]
    ) -> tuple[ChartPatternView, ...]:
        """선택 종목의 틱 곡선에서 관측되는 형태. 이미 계산한 시리즈를 재사용한다.

        일봉이 아니라 **틱 곡선**에 돌린다 — 봉은 최대 14개라 어깨·머리를 이룰 극값이
        애초에 나오지 않는다.

        ⚠️ 여기서 나오는 것은 관측된 형태일 뿐 예측이 아니다. 게임 주가는 브라운 운동에
        이벤트 충격을 더해 만든 값이므로 이 형태에는 시장 심리가 담겨 있지 않다.
        """
        if query.candle_symbol is None:
            return ()
        target = next((s for s in symbols if s.symbol == query.candle_symbol), None)
        if target is None or len(target.series) < MIN_PATTERN_POINTS:
            return ()

        closes = [float(p.price_krw) for p in target.series]
        return tuple(
            ChartPatternView(
                name=p.name,
                label=p.label,
                start_index=p.start_index,
                end_index=p.end_index,
                confidence=p.confidence,
                points=tuple((i, round(price)) for i, price in p.points),
                note=p.note,
            )
            for p in chart_pattern.detect(closes)[:MAX_PATTERNS]
        )

    def _candles_for(
        self,
        query: MarketPriceQuery,
        end_tick: int,
        extra: tuple[market_events.MarketEvent, ...] = (),
    ) -> tuple[tuple[CandleView, ...], SymbolInfo | None]:
        """선택 종목 하나의 일봉과 종목 카드. 지정하지 않으면 계산하지 않는다.

        전 종목에 돌리지 않는 이유는 비용이다 — 하루당 60회 평가라 전 종목 × 7일이면
        응답 목표(p95 200ms)를 넘긴다.
        """
        if query.candle_symbol is None:
            return (), None
        params = next((s for s in SYMBOLS if s.symbol == query.candle_symbol), None)
        if params is None:
            raise UnknownSymbol(f"알 수 없는 종목입니다: {query.candle_symbol}")
        if not MIN_CANDLE_DAYS <= query.candle_days <= MAX_CANDLE_DAYS:
            raise InvalidTickRange(
                f"candle_days는 {MIN_CANDLE_DAYS}~{MAX_CANDLE_DAYS} 범위여야 합니다"
            )

        raw = price_engine.daily_candles(params, end_tick, query.candle_days, extra)
        candles = tuple(
            CandleView(
                game_day=c.game_day,
                open_krw=c.open_krw,
                high_krw=c.high_krw,
                low_krw=c.low_krw,
                close_krw=c.close_krw,
            )
            for c in raw
        )
        info = SymbolInfo(
            symbol=params.symbol,
            name=params.name,
            sector=params.sector,
            sector_group=params.sector_group,
            meme=params.meme,
            base_price_krw=params.base_price_krw,
            # 시즌 고저가는 43,200틱 순회라 넣지 않는다 — 봉에서 나오는 최근 구간으로 대신한다
            # 밈 배수까지 반영한 **체감** 변동성이다 — 화면 숫자와 실제 곡선이 갈라지지 않게
            game_daily_sigma_pct=round(
                params.sigma_daily
                * (MEME_SIGMA_MULTIPLIER if params.meme else 1.0)
                * SIGMA_GAME_MULTIPLIER
                * 100.0,
                2,
            ),
            recent_high_krw=max(c.high_krw for c in raw),
            recent_low_krw=min(c.low_krw for c in raw),
            recent_days=len(raw),
        )
        return candles, info
