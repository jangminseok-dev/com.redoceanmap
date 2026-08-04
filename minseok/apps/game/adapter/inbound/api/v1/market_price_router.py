from fastapi import APIRouter, Depends, HTTPException, Query

from game.adapter.inbound.api.schemas.market_price_schema import (
    CandleSchema,
    MovingAverageSchema,
    OrderBookSchema,
    QuoteSchema,
    SignalAxisSchema,
    SymbolAnalysisSchema,
    ChartPatternSchema,
    MarketEventSchema,
    MarketPricesResponseSchema,
    PricePointSchema,
    SymbolInfoSchema,
    SymbolPricesSchema,
)
from game.app.dtos.market_price_dto import MarketPriceQuery
from game.app.exceptions import InvalidTickRange, UnknownSymbol
from game.app.ports.input.market_price_use_case import MarketPriceUseCase
from game.app.use_cases.market_price_interactor import (
    MAX_CANDLE_DAYS,
    MAX_TICKS,
    MIN_CANDLE_DAYS,
    MIN_TICKS,
)
from game.dependencies.market_price_provider import get_market_price_use_case

def _pattern_schema(p) -> ChartPatternSchema:
    """탐지 형태 → 스키마. 틱·일봉 두 축이 같은 변환을 쓴다."""
    return ChartPatternSchema(
        name=p.name,
        label=p.label,
        startIndex=p.start_index,
        endIndex=p.end_index,
        confidence=p.confidence,
        points=[(i, price) for i, price in p.points],
        note=p.note,
    )


market_price_router = APIRouter(prefix="/game", tags=["game"])


@market_price_router.get("/market/prices", response_model=MarketPricesResponseSchema)
async def list_prices(
    ticks: int = Query(60, ge=MIN_TICKS, le=MAX_TICKS, description="반환할 최근 틱 개수"),
    candle_symbol: str | None = Query(
        None, description="일봉·종목정보를 계산할 종목. 비용 때문에 한 종목만 받는다"
    ),
    candle_days: int = Query(
        7, ge=MIN_CANDLE_DAYS, le=MAX_CANDLE_DAYS, description="일봉 개수(게임일)"
    ),
    use_case: MarketPriceUseCase = Depends(get_market_price_use_case),
) -> MarketPricesResponseSchema:
    try:
        result = await use_case.list_prices(
            MarketPriceQuery(ticks=ticks, candle_symbol=candle_symbol, candle_days=candle_days)
        )
    except UnknownSymbol as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
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
                sectorGroup=s.sector_group,
                meme=s.meme,
                priceKrw=s.price_krw,
                changePct=s.change_pct,
                series=[
                    PricePointSchema(tick=p.tick, priceKrw=p.price_krw) for p in s.series
                ],
                simulatedVolume=s.simulated_volume,
                assumedMarketCapKrw=s.assumed_market_cap_krw,
            )
            for s in result.symbols
        ],
        events=[
            MarketEventSchema(
                tick=e.tick,
                scope=e.scope,
                target=e.target,
                targetName=e.target_name,
                positive=e.positive,
                headline=e.headline,
                affectedSymbols=list(e.affected_symbols),
                expectedImpactPct=e.expected_impact_pct,
                remainingImpactPct=e.remaining_impact_pct,
            )
            for e in result.events
        ],
        candles=[
            CandleSchema(
                gameDay=c.game_day,
                openKrw=c.open_krw,
                highKrw=c.high_krw,
                lowKrw=c.low_krw,
                closeKrw=c.close_krw,
                simulatedVolume=c.simulated_volume,
            )
            for c in result.candles
        ],
        movingAverages=[
            MovingAverageSchema(period=m.period, points=list(m.points))
            for m in result.moving_averages
        ],
        rsi=list(result.rsi),
        analysis=(
            SymbolAnalysisSchema(
                score=result.analysis.score,
                label=result.analysis.label,
                axes=[
                    SignalAxisSchema(
                        key=a.key, label=a.label, value=a.value, weight=a.weight, note=a.note
                    )
                    for a in result.analysis.axes
                ],
                rsi=result.analysis.rsi,
                percentB=result.analysis.percent_b,
                atrPct=result.analysis.atr_pct,
                volumeRatio=result.analysis.volume_ratio,
                obvSlope=result.analysis.obv_slope,
                newsImpactPct=result.analysis.news_impact_pct,
                headlineCount=result.analysis.headline_count,
                dailyPatterns=[_pattern_schema(p) for p in result.analysis.daily_patterns],
            )
            if result.analysis
            else None
        ),
        orderBook=(
            OrderBookSchema(
                bids=[QuoteSchema(priceKrw=q.price_krw, assumedQuantity=q.assumed_quantity)
                      for q in result.order_book.bids],
                asks=[QuoteSchema(priceKrw=q.price_krw, assumedQuantity=q.assumed_quantity)
                      for q in result.order_book.asks],
                spreadKrw=result.order_book.spread_krw,
                tickSizeKrw=result.order_book.tick_size_krw,
                halted=result.order_book.halted,
                limitState=result.order_book.limit_state,
                shortInterestPct=result.order_book.short_interest_pct,
            )
            if result.order_book
            else None
        ),
        symbolInfo=(
            SymbolInfoSchema(
                symbol=result.symbol_info.symbol,
                name=result.symbol_info.name,
                sector=result.symbol_info.sector,
                sectorGroup=result.symbol_info.sector_group,
                meme=result.symbol_info.meme,
                basePriceKrw=result.symbol_info.base_price_krw,
                gameDailySigmaPct=result.symbol_info.game_daily_sigma_pct,
                recentHighKrw=result.symbol_info.recent_high_krw,
                recentLowKrw=result.symbol_info.recent_low_krw,
                recentDays=result.symbol_info.recent_days,
                gameQuarter=result.symbol_info.game_quarter,
                assumedSharesOutstanding=result.symbol_info.assumed_shares_outstanding,
                assumedEpsKrw=result.symbol_info.assumed_eps_krw,
                assumedBpsKrw=result.symbol_info.assumed_bps_krw,
                assumedRoe=result.symbol_info.assumed_roe,
                assumedDebtRatio=result.symbol_info.assumed_debt_ratio,
                assumedNetIncomeKrw=result.symbol_info.assumed_net_income_krw,
                assumedMarketCapKrw=result.symbol_info.assumed_market_cap_krw,
                per=result.symbol_info.per,
                pbr=result.symbol_info.pbr,
                earningsSurprise=result.symbol_info.earnings_surprise,
            )
            if result.symbol_info
            else None
        ),
        patterns=[_pattern_schema(p) for p in result.patterns],
    )
