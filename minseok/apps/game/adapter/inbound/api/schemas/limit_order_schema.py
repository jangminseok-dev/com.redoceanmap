from pydantic import BaseModel, Field


class PlaceEntryOrderRequestSchema(BaseModel):
    """진입 예약 — 지정가에 닿으면 그 가격으로 체결된다."""

    symbol: str
    side: str  # LONG | SHORT
    quantity: int = Field(gt=0)
    limitPriceKrw: int = Field(gt=0)
    leverage: int = 1


class PlaceExitOrderRequestSchema(BaseModel):
    """청산 예약 — 둘 다 넣으면 한 쌍(OCO)이 되어 한쪽 체결 시 나머지가 취소된다."""

    positionId: int
    takeProfitKrw: int | None = None
    stopLossKrw: int | None = None


class LimitOrderSchema(BaseModel):
    id: int
    kind: str  # ENTRY | EXIT
    symbol: str
    name: str
    side: str
    positionId: int | None
    trigger: str  # le(이하) | ge(이상)
    limitPriceKrw: int
    quantity: int
    leverage: int
    placedTick: int
    expiresTick: int
    status: str  # pending | filled | cancelled | expired
    filledTick: int | None
    filledPriceKrw: int | None
    reservedCashKrw: int


class OrderListResponseSchema(BaseModel):
    """`settledCount`는 이번 조회에서 확정된 건수 — 조회가 곧 체결 시점이다."""

    tick: int
    pending: list[LimitOrderSchema]
    recent: list[LimitOrderSchema]
    settledCount: int


class OrderReceiptSchema(BaseModel):
    orders: list[LimitOrderSchema]
    cashKrw: int
