from __future__ import annotations

from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.market_price_use_case import MarketPriceUseCase
from game.app.use_cases.market_price_interactor import MarketPriceInteractor


def get_market_price_use_case() -> MarketPriceUseCase:
    return MarketPriceInteractor(clock=SystemGameClockAdapter())
