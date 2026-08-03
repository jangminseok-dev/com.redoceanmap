from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from stock.adapter.inbound.api.schemas.stock_history_schema import (
    ChartPatternSchema,
    FundamentalInsightSchema,
    FundamentalSnapshotSchema,
    FundamentalsResponse,
    PriceBarSchema,
    PriceHistoryResponse,
    StockNewsItemSchema,
)
from stock.app.dtos.stock_history_dto import (
    FundamentalsQuery,
    PriceHistoryQuery,
    StockNewsQuery,
)
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.ports.input.stock_history_use_case import StockHistoryUseCase
from stock.dependencies.stock_history_provider import get_stock_history_use_case

stock_history_router = APIRouter(prefix="/stock", tags=["stock"])


@stock_history_router.get("/{symbol}/prices", response_model=PriceHistoryResponse)
async def get_price_history(
    symbol: str,
    timeframe: Literal["1d", "5m"] = "1d",
    limit: int = Query(default=500, ge=1, le=5000),
    use_case: StockHistoryUseCase = Depends(get_stock_history_use_case),
) -> PriceHistoryResponse:
    try:
        history = await use_case.price_history(
            PriceHistoryQuery(symbol=symbol, timeframe=timeframe, limit=limit)
        )
    except MarketDataUnavailableError as e:
        raise HTTPException(status_code=404, detail=e.detail)
    return PriceHistoryResponse(
        symbol=history.symbol,
        resolvedTicker=history.resolved_ticker,
        timeframe=history.timeframe,
        live=history.live,
        bars=[
            PriceBarSchema(
                ts=b.ts, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume
            )
            for b in history.bars
        ],
        patterns=[
            ChartPatternSchema(
                name=p.name,
                label=p.label,
                startIndex=p.start_index,
                endIndex=p.end_index,
                confidence=p.confidence,
                points=[(i, price) for i, price in p.points],
                note=p.note,
            )
            for p in history.patterns
        ],
    )


@stock_history_router.get("/{symbol}/news", response_model=list[StockNewsItemSchema])
async def get_stock_news(
    symbol: str,
    limit: int = Query(default=20, ge=1, le=100),
    use_case: StockHistoryUseCase = Depends(get_stock_history_use_case),
) -> list[StockNewsItemSchema]:
    items = await use_case.news(StockNewsQuery(symbol=symbol, limit=limit))
    return [
        StockNewsItemSchema(
            id=i.id, title=i.title, source=i.source, url=i.url,
            publishedAt=i.published_at,
            sentiment=i.sentiment, eventType=i.event_type, confidence=i.confidence,
        )
        for i in items
    ]


@stock_history_router.get("/{symbol}/fundamentals", response_model=FundamentalsResponse)
async def get_fundamentals(
    symbol: str,
    use_case: StockHistoryUseCase = Depends(get_stock_history_use_case),
) -> FundamentalsResponse:
    view = await use_case.fundamentals(FundamentalsQuery(symbol=symbol))
    return FundamentalsResponse(
        symbol=view.symbol,
        snapshots=[
            FundamentalSnapshotSchema(
                asOf=s.as_of, source=s.source, per=s.per, pbr=s.pbr, roe=s.roe,
                debtToEquity=s.debt_to_equity, fcf=s.fcf, marketCap=s.market_cap,
                eps=s.eps, bps=s.bps,
            )
            for s in view.snapshots
        ],
        insights=[
            FundamentalInsightSchema(key=i.key, tone=i.tone, text=i.text)
            for i in view.insights
        ],
    )
