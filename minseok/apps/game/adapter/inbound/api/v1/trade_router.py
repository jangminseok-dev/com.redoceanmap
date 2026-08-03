from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.trade_schema import (
    OpenTradeRequestSchema,
    TradeReceiptSchema,
)
from game.app.dtos.trade_dto import CloseTradeCommand, OpenTradeCommand, TradeReceipt
from game.app.exceptions import (
    InsufficientCash,
    InvalidOrder,
    PositionNotFound,
    SeasonClosed,
    UnknownSymbol,
)
from game.app.ports.input.trade_use_case import TradeUseCase
from game.dependencies.trade_provider import get_trade_use_case

trade_router = APIRouter(prefix="/game", tags=["game"])


def _to_schema(receipt: TradeReceipt) -> TradeReceiptSchema:
    return TradeReceiptSchema(
        positionId=receipt.position_id,
        symbol=receipt.symbol,
        name=receipt.name,
        side=receipt.side,
        quantity=receipt.quantity,
        priceKrw=receipt.price_krw,
        feeKrw=receipt.fee_krw,
        carryKrw=receipt.carry_krw,
        cashDeltaKrw=receipt.cash_delta_krw,
        realizedPnlKrw=receipt.realized_pnl_krw,
        cashKrw=receipt.cash_krw,
        tick=receipt.tick,
        leverage=receipt.leverage,
        liquidationPriceKrw=receipt.liquidation_price_krw,
        expiresTick=receipt.expires_tick,
    )


@trade_router.post("/trades", response_model=TradeReceiptSchema)
async def open_trade(
    body: OpenTradeRequestSchema,
    user_id: int = Depends(get_current_user_id),
    use_case: TradeUseCase = Depends(get_trade_use_case),
) -> TradeReceiptSchema:
    try:
        receipt = await use_case.open(
            OpenTradeCommand(
                user_id=user_id,
                symbol=body.symbol,
                side=body.side,
                quantity=body.quantity,
                leverage=body.leverage,
            )
        )
    except UnknownSymbol as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    except (InvalidOrder, InsufficientCash, SeasonClosed) as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    return _to_schema(receipt)


@trade_router.post("/trades/{position_id}/close", response_model=TradeReceiptSchema)
async def close_trade(
    position_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: TradeUseCase = Depends(get_trade_use_case),
) -> TradeReceiptSchema:
    try:
        receipt = await use_case.close(
            CloseTradeCommand(user_id=user_id, position_id=position_id)
        )
    except (PositionNotFound, UnknownSymbol) as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    return _to_schema(receipt)
