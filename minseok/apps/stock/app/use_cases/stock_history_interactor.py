from __future__ import annotations

import logging
import time

from core import chart_pattern
from stock.app.dtos.stock_history_dto import (
    FundamentalsQuery,
    FundamentalsView,
    PriceHistory,
    PriceHistoryQuery,
    StockNewsItem,
    StockNewsQuery,
)
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.ports.input.stock_history_use_case import StockHistoryUseCase
from stock.app.ports.output.market_data_port import MarketDataPort
from stock.app.ports.output.stock_history_repository import StockHistoryRepositoryPort
from stock.domain.services import fundamental_narrator
from stock.domain.value_objects.market_values import Symbol

logger = logging.getLogger(__name__)

# 라이브 폴백 봉 서버 캐시 — 미수집 종목의 요청마다 2y 다운로드가 나가지 않게
# 심볼당 TTL 동안 재사용한다(일봉은 일 단위 갱신이라 10분이면 충분히 신선).
_LIVE_BARS_TTL_SECONDS = 600.0
_LIVE_BARS_CACHE: dict[str, tuple[float, list]] = {}

# 차트 형태는 신뢰도 상위만 내려준다 — 전부 그리면 차트가 보조선에 덮인다.
MAX_PATTERNS = 3


class StockHistoryInteractor(StockHistoryUseCase):
    """수집 데이터 조회 대장 — 심볼 정규화 후 저장소 조회를 조립한다.

    분석(StockInteractor·yfinance 라이브)과 달리 DB에 축적된 것을 우선 읽되,
    미수집 종목의 일봉은 시세 벤더 라이브 이력으로 폴백한다(live=True, 저장 안 함) —
    임의 티커도 차트가 뜨게. 5m는 폴백 없이 404, 벤더도 모르는 심볼은 404.
    """

    def __init__(
        self,
        history: StockHistoryRepositoryPort,
        market_data: MarketDataPort | None = None,
    ) -> None:
        self._history = history
        self._market_data = market_data

    async def price_history(self, query: PriceHistoryQuery) -> PriceHistory:
        symbol = _normalize(query.symbol)
        bars = await self._history.find_bars(symbol, query.timeframe, query.limit)
        live = False
        if not bars and query.timeframe == "1d" and self._market_data is not None:
            now = time.monotonic()
            cached = _LIVE_BARS_CACHE.get(symbol)
            if cached is not None and now - cached[0] < _LIVE_BARS_TTL_SECONDS:
                full = cached[1]
            else:
                full = await self._market_data.daily_bars(Symbol(code=symbol))
                _LIVE_BARS_CACHE[symbol] = (now, full)
                logger.info("[stock-history] %s 일봉 라이브 폴백 %d봉", symbol, len(full))
            bars = full[-query.limit:]
            live = True
        if not bars:
            raise MarketDataUnavailableError(
                f"수집된 {query.timeframe} 봉이 없습니다(수집 대상 아님): {query.symbol}"
            )
        return PriceHistory(
            symbol=symbol,
            resolved_ticker=bars[0].ticker,
            timeframe=query.timeframe,
            bars=bars,
            live=live,
            patterns=chart_pattern.detect([b.close for b in bars])[:MAX_PATTERNS],
        )

    async def news(self, query: StockNewsQuery) -> list[StockNewsItem]:
        return await self._history.find_news(_normalize(query.symbol), query.limit)

    async def fundamentals(self, query: FundamentalsQuery) -> FundamentalsView:
        symbol = _normalize(query.symbol)
        snapshots = await self._history.find_latest_fundamentals(symbol)
        return FundamentalsView(
            symbol=symbol,
            snapshots=snapshots,
            insights=fundamental_narrator.narrate(snapshots),
        )


def _normalize(symbol: str) -> str:
    """티커 표기 통일 — DB 티커는 대문자(AAPL, 005930.KS)로 저장된다."""
    return symbol.strip().upper()
