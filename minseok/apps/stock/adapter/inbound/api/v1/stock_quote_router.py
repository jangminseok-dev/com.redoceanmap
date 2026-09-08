from fastapi import APIRouter, Depends, HTTPException

from stock.adapter.inbound.api.schemas.stock_quote_schema import StockQuoteResponse
from stock.app.dtos.stock_quote_dto import QuoteQuery
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.ports.input.stock_quote_use_case import StockQuoteUseCase
from stock.dependencies.stock_quote_provider import get_stock_quote_use_case

stock_quote_router = APIRouter(prefix="/stock", tags=["stock"])


@stock_quote_router.get("/{symbol}/quote", response_model=StockQuoteResponse)
async def get_stock_quote(
    symbol: str,
    use_case: StockQuoteUseCase = Depends(get_stock_quote_use_case),
) -> StockQuoteResponse:
    try:
        view = await use_case.quote(QuoteQuery(symbol=symbol))
    except MarketDataUnavailableError as e:
        raise HTTPException(status_code=404, detail=e.detail)
    return StockQuoteResponse(
        symbol=view.symbol,
        price=view.price,
        delayed=view.delayed,
        previous_close=view.previous_close,
        change_pct=view.change_pct,
        fetched_at=view.fetched_at,
    )
