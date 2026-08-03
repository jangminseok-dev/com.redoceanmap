from fastapi import APIRouter, Depends

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.wallet_schema import (
    ClosedNoticeSchema,
    PositionSchema,
    WalletResponseSchema,
)
from game.app.dtos.wallet_dto import WalletQuery
from game.app.ports.input.wallet_use_case import WalletUseCase
from game.dependencies.wallet_provider import get_wallet_use_case

wallet_router = APIRouter(prefix="/game", tags=["game"])


@wallet_router.get("/wallet", response_model=WalletResponseSchema)
async def get_wallet(
    user_id: int = Depends(get_current_user_id),
    use_case: WalletUseCase = Depends(get_wallet_use_case),
) -> WalletResponseSchema:
    result = await use_case.get_wallet(WalletQuery(user_id=user_id))
    return WalletResponseSchema(
        cashKrw=result.cash_krw,
        investableKrw=result.investable_krw,
        reservedKrw=result.reserved_krw,
        positionValueKrw=result.position_value_krw,
        totalAssetKrw=result.total_asset_krw,
        initialCashKrw=result.initial_cash_krw,
        totalReturnPct=result.total_return_pct,
        epochId=result.epoch_id,
        ruleVersion=result.rule_version,
        tick=result.tick,
        gameDay=result.game_day,
        gameQuarter=result.game_quarter,
        seasonOver=result.season_over,
        positions=[
            PositionSchema(
                id=p.id,
                symbol=p.symbol,
                name=p.name,
                sector=p.sector,
                side=p.side,
                quantity=p.quantity,
                entryTick=p.entry_tick,
                entryPriceKrw=p.entry_price_krw,
                currentPriceKrw=p.current_price_krw,
                marketValueKrw=p.market_value_krw,
                unrealizedPnlKrw=p.unrealized_pnl_krw,
                unrealizedPct=p.unrealized_pct,
                leverage=p.leverage,
                liquidationPriceKrw=p.liquidation_price_krw,
                expiresTick=p.expires_tick,
            )
            for p in result.positions
        ],
        recentlyClosed=[
            ClosedNoticeSchema(
                id=c.id,
                symbol=c.symbol,
                name=c.name,
                side=c.side,
                quantity=c.quantity,
                leverage=c.leverage,
                closedGameDay=c.closed_game_day,
                exitPriceKrw=c.exit_price_krw,
                realizedPnlKrw=c.realized_pnl_krw,
                reason=c.reason,
            )
            for c in result.recently_closed
        ],
    )
