from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user_id
from game.adapter.inbound.api.schemas.limit_order_schema import (
    LimitOrderSchema,
    OrderListResponseSchema,
    OrderReceiptSchema,
    PlaceEntryOrderRequestSchema,
    PlaceExitOrderRequestSchema,
)
from game.app.dtos.limit_order_dto import (
    LimitOrderView,
    OrderActionCommand,
    OrderListQuery,
    OrderReceipt,
    PlaceEntryOrderCommand,
    PlaceExitOrderCommand,
)
from game.app.exceptions import (
    InsufficientCash,
    InvalidOrder,
    PositionNotFound,
    SeasonClosed,
    UnknownSymbol,
)
from game.app.ports.input.limit_order_use_case import LimitOrderUseCase
from game.dependencies.limit_order_provider import get_limit_order_use_case

limit_order_router = APIRouter(prefix="/game", tags=["game"])


def _to_schema(view: LimitOrderView) -> LimitOrderSchema:
    return LimitOrderSchema(
        id=view.id,
        kind=view.kind,
        symbol=view.symbol,
        name=view.name,
        side=view.side,
        positionId=view.position_id,
        trigger=view.trigger,
        limitPriceKrw=view.limit_price_krw,
        quantity=view.quantity,
        leverage=view.leverage,
        placedTick=view.placed_tick,
        expiresTick=view.expires_tick,
        status=view.status,
        filledTick=view.filled_tick,
        filledPriceKrw=view.filled_price_krw,
        reservedCashKrw=view.reserved_cash_krw,
    )


def _to_receipt(receipt: OrderReceipt) -> OrderReceiptSchema:
    return OrderReceiptSchema(
        orders=[_to_schema(o) for o in receipt.orders], cashKrw=receipt.cash_krw
    )


@limit_order_router.get("/orders", response_model=OrderListResponseSchema)
async def list_orders(
    user_id: int = Depends(get_current_user_id),
    use_case: LimitOrderUseCase = Depends(get_limit_order_use_case),
) -> OrderListResponseSchema:
    """대기·최근 주문. **이 호출이 곧 체결 판정 시점이다**(cron 0개 — 지연 실행)."""
    result = await use_case.list_orders(OrderListQuery(user_id=user_id))
    return OrderListResponseSchema(
        tick=result.tick,
        pending=[_to_schema(o) for o in result.pending],
        recent=[_to_schema(o) for o in result.recent],
        settledCount=result.settled_count,
    )


@limit_order_router.post("/orders", response_model=OrderReceiptSchema, status_code=201)
async def place_entry_order(
    body: PlaceEntryOrderRequestSchema,
    user_id: int = Depends(get_current_user_id),
    use_case: LimitOrderUseCase = Depends(get_limit_order_use_case),
) -> OrderReceiptSchema:
    """진입 예약 — 체결에 쓸 현금을 지금 묶는다(취소·만료 시 돌려준다)."""
    try:
        receipt = await use_case.place_entry(
            PlaceEntryOrderCommand(
                user_id=user_id,
                symbol=body.symbol,
                side=body.side,
                quantity=body.quantity,
                limit_price_krw=body.limitPriceKrw,
                leverage=body.leverage,
            )
        )
    except (InvalidOrder, UnknownSymbol, InsufficientCash, SeasonClosed) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_receipt(receipt)


@limit_order_router.post("/orders/exits", response_model=OrderReceiptSchema, status_code=201)
async def place_exit_order(
    body: PlaceExitOrderRequestSchema,
    user_id: int = Depends(get_current_user_id),
    use_case: LimitOrderUseCase = Depends(get_limit_order_use_case),
) -> OrderReceiptSchema:
    """보유 포지션의 익절·손절. 같은 포지션에 다시 걸면 기존 예약을 갈아끼운다."""
    try:
        receipt = await use_case.place_exit(
            PlaceExitOrderCommand(
                user_id=user_id,
                position_id=body.positionId,
                take_profit_krw=body.takeProfitKrw,
                stop_loss_krw=body.stopLossKrw,
            )
        )
    except PositionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidOrder, UnknownSymbol) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_receipt(receipt)


@limit_order_router.post("/orders/{order_id}/cancel", response_model=OrderReceiptSchema)
async def cancel_order(
    order_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: LimitOrderUseCase = Depends(get_limit_order_use_case),
) -> OrderReceiptSchema:
    try:
        receipt = await use_case.cancel(OrderActionCommand(user_id=user_id, order_id=order_id))
    except InvalidOrder as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_receipt(receipt)


@limit_order_router.post("/orders/{order_id}/extend", response_model=OrderReceiptSchema)
async def extend_order(
    order_id: int,
    user_id: int = Depends(get_current_user_id),
    use_case: LimitOrderUseCase = Depends(get_limit_order_use_case),
) -> OrderReceiptSchema:
    """만료 연장 — 만료는 스캔 범위를 묶는 성능 장치라 없앨 수 없고 미루기만 한다."""
    try:
        receipt = await use_case.extend(OrderActionCommand(user_id=user_id, order_id=order_id))
    except InvalidOrder as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_receipt(receipt)
