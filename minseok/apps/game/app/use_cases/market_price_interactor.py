from __future__ import annotations

from game.app.dtos.market_price_dto import (
    MarketPricesResponse,
    MarketPriceQuery,
    PricePoint,
    SymbolPrices,
)
from game.app.exceptions import InvalidTickRange
from game.app.ports.input.market_price_use_case import MarketPriceUseCase
from game.app.ports.output.game_clock_port import GameClockPort
from game.domain.clock.game_epoch import (
    GAME_EPOCH_ID,
    RULES_VERSION,
    SEASON_TICKS,
    TICKS_PER_GAME_DAY,
    describe,
)
from game.domain.market import price_engine
from game.domain.market.symbol_params import CALIBRATED_AT, SYMBOLS

MIN_TICKS = 2
MAX_TICKS = 240  # 12종목 × 240틱이 응답 목표(p95 200ms) 안에 드는 상한


class MarketPriceInteractor(MarketPriceUseCase):
    """게임 시세 대장 — 현재 틱을 받아 전 종목 곡선을 계산한다.

    가격을 저장하지도, 캐시하지도 않는다. 계산이 정본이다(game-harness §4-2).
    """

    def __init__(self, clock: GameClockPort) -> None:
        self._clock = clock

    async def list_prices(self, query: MarketPriceQuery) -> MarketPricesResponse:
        if not MIN_TICKS <= query.ticks <= MAX_TICKS:
            raise InvalidTickRange(f"ticks는 {MIN_TICKS}~{MAX_TICKS} 범위여야 합니다")

        # 현재 틱까지만 계산한다 — 미래 틱은 만들지 않는다(§1-6).
        # 시즌이 끝났으면 마지막 틱에 멈춘다(그 뒤로는 가격이 변하지 않는다).
        now_tick = self._clock.now_tick()
        moment = describe(now_tick)
        end_tick = min(now_tick, SEASON_TICKS)

        symbols = tuple(
            SymbolPrices(
                symbol=params.symbol,
                name=params.name,
                sector=params.sector,
                price_krw=price_engine.price_at(params, end_tick),
                change_pct=round(
                    price_engine.change_pct(params, end_tick, TICKS_PER_GAME_DAY), 2
                ),
                series=tuple(
                    PricePoint(tick=t, price_krw=p)
                    for t, p in price_engine.price_series(params, end_tick, query.ticks)
                ),
            )
            for params in SYMBOLS
        )
        return MarketPricesResponse(
            virtual=True,
            calibrated=CALIBRATED_AT is not None,
            epoch_id=GAME_EPOCH_ID,
            rule_version=RULES_VERSION,
            tick=moment.tick,
            game_day=moment.game_day,
            game_quarter=moment.game_quarter,
            season_over=moment.season_over,
            symbols=symbols,
        )
