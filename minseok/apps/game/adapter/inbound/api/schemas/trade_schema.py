from pydantic import BaseModel, Field


class OpenTradeRequestSchema(BaseModel):

    symbol: str = Field(description="게임 종목 코드 (예: GX01)")
    side: str = Field(description="LONG | SHORT")
    quantity: int = Field(gt=0, description="주 수")

    model_config = {
        "json_schema_extra": {
            "example": {"symbol": "GX01", "side": "LONG", "quantity": 10}
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
