from pydantic import BaseModel, Field


class OpenTradeRequestSchema(BaseModel):

    symbol: str = Field(description="게임 종목 코드 (예: GX01)")
    side: str = Field(description="LONG | SHORT")
    quantity: int = Field(gt=0, description="주 수")
    leverage: int = Field(
        1, ge=1, le=4, description="1·2·3·4배. 2배 이상은 만료(게임 3일)와 강제청산이 붙는다"
    )

    model_config = {
        "json_schema_extra": {
            "example": {"symbol": "GX01", "side": "LONG", "quantity": 10, "leverage": 1}
        }
    }


class TradeReceiptSchema(BaseModel):

    positionId: int
    symbol: str
    name: str
    side: str
    quantity: int
    priceKrw: int = Field(description="체결가 — 요청이 도착한 틱의 가격")
    feeKrw: int
    carryKrw: int = Field(description="숏 보유비용 (청산에만)")
    cashDeltaKrw: int = Field(description="지갑 증감 — 진입은 음수")
    realizedPnlKrw: int | None = Field(description="실현손익 (청산에만)")
    cashKrw: int = Field(description="체결 후 잔고")
    tick: int
    leverage: int = 1
    liquidationPriceKrw: int | None = Field(
        None, description="이 가격에 닿으면 강제청산된다. 1배는 청산되지 않아 null"
    )
    expiresTick: int | None = Field(
        None, description="레버리지 포지션의 자동 마감 시점. 1배는 null"
    )
