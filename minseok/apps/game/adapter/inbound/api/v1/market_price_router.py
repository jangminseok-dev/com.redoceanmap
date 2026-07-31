from fastapi import APIRouter, Depends, HTTPException, Query

from game.adapter.inbound.api.schemas.market_price_schema import (
    MarketPricesResponseSchema,
    PricePointSchema,
    SymbolPricesSchema,
)
from game.app.dtos.market_price_dto import MarketPriceQuery
from game.app.exceptions import InvalidTickRange
from game.app.ports.input.market_price_use_case import MarketPriceUseCase
from game.app.use_cases.market_price_interactor import MAX_TICKS, MIN_TICKS
from game.dependencies.market_price_provider import get_market_price_use_case

market_price_router = APIRouter(prefix="/game", tags=["game"])


@market_price_router.get("/market/prices", response_model=MarketPricesResponseSchema)
async def list_prices(
    ticks: int = Query(60, ge=MIN_TICKS, le=MAX_TICKS, description="반환할 최근 틱 개수"),
    use_case: MarketPriceUseCase = Depends(get_market_price_use_case),
) -> MarketPricesResponseSchema:
    try:
        result = await use_case.list_prices(MarketPriceQuery(ticks=ticks))
    except InvalidTickRange as e:
        raise HTTPException(status_code=400, detail=e.detail) from e

    return MarketPricesResponseSchema(
        virtual=result.virtual,
        calibrated=result.calibrated,
        epochId=result.epoch_id,
        ruleVersion=result.rule_version,
        tick=result.tick,
        gameDay=result.game_day,
        gameQuarter=result.game_quarter,
        seasonOver=result.season_over,
        symbols=[
            SymbolPricesSchema(
                symbol=s.symbol,
                name=s.name,
                sector=s.sector,
                priceKrw=s.price_krw,
                changePct=s.change_pct,
                series=[
                    PricePointSchema(tick=p.tick, priceKrw=p.price_krw) for p in s.series
                ],
            )
            for s in result.symbols
        ],
    )
