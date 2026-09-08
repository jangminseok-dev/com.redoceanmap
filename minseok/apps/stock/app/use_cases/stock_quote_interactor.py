from __future__ import annotations

import time
from datetime import UTC, datetime

from stock.app.dtos.stock_quote_dto import QuoteQuery, QuoteView
from stock.app.ports.input.stock_quote_use_case import StockQuoteUseCase
from stock.app.ports.output.market_data_port import MarketDataPort
from stock.domain.value_objects.market_values import Symbol

# 서버 측 공유 캐시 — 여러 사용자가 같은 종목을 폴링해도 벤더 호출은
# 심볼당 TTL에 1회로 상한(다중 사용자에서 yfinance 429 방지).
# TTL은 프론트 폴링 간격(30초) 이상이어야 단일 사용자도 절반은 캐시를 탄다 — 지연 시세라 무해.
_CACHE_TTL_SECONDS = 30.0
_CACHE: dict[str, tuple[float, QuoteView]] = {}


class StockQuoteInteractor(StockQuoteUseCase):
    """현재가 조회 대장 — 기존 MarketDataPort의 경량 quote만 쓴다(이력 미조회)."""

    def __init__(self, market_data: MarketDataPort) -> None:
        self._market_data = market_data

    async def quote(self, query: QuoteQuery) -> QuoteView:
        symbol = query.symbol.strip().upper()
        cached = _CACHE.get(symbol)
        now = time.monotonic()
        if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
        quote = await self._market_data.quote(Symbol(code=symbol))
        view = QuoteView(
            symbol=symbol,
            price=quote.price.value,
            delayed=True,
            previous_close=quote.previous_close.value if quote.previous_close else None,
            change_pct=quote.change_pct(),
            fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        _CACHE[symbol] = (now, view)
        return view
