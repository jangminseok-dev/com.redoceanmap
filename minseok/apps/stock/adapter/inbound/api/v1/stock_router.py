import logging
from dataclasses import asdict

from fastapi import Query, APIRouter, Depends, HTTPException

from stock.adapter.inbound.api.schemas.stock_schema import StockAnalyzeResponse
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.ports.input.stock_use_case import StockUseCase
from stock.dependencies.stock_provider import get_stock_use_case
from stock.domain.value_objects.market_values import Symbol

logger = logging.getLogger(__name__)

stock_router = APIRouter(prefix="/stock", tags=["stock"])


@stock_router.post("/analyze", response_model=StockAnalyzeResponse)
async def analyze(
    symbol: str = Query(min_length=1, description="종목 코드·티커·이름 — 생략 불가(2026-09-08 QA: 기본값 AAPL이 다른 종목을 조용히 돌려줬다)"),
    use_case: StockUseCase = Depends(get_stock_use_case),
) -> StockAnalyzeResponse:
    try:
        result = await use_case.analyze(Symbol(code=symbol))
    except MarketDataUnavailableError as e:
        # 앱 계층 예외 → HTTP 변환은 인바운드 어댑터의 책임
        raise HTTPException(status_code=404, detail=e.detail)
    return StockAnalyzeResponse(**asdict(result))
