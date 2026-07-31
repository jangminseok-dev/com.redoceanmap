from pydantic import BaseModel, Field


class PositionSchema(BaseModel):

    id: int
    symbol: str
    name: str
    sector: str
    side: str = Field(description="LONG | SHORT")
    quantity: int
    entryTick: int
    entryPriceKrw: int
    currentPriceKrw: int
    marketValueKrw: int = Field(description="지금 청산하면 돌아올 금액(수수료·보유비용 반영)")
    unrealizedPnlKrw: int
    unrealizedPct: float


class WalletResponseSchema(BaseModel):

    cashKrw: int
    investableKrw: int = Field(description="최소 생활자금을 뺀 투자 가능액")
    reservedKrw: int = Field(description="투자에 쓸 수 없는 최소 생활자금")
    positionValueKrw: int
    totalAssetKrw: int
    initialCashKrw: int
    totalReturnPct: float
    epochId: int
    ruleVersion: str
    tick: int
    gameDay: int
    gameQuarter: int
    seasonOver: bool
    positions: list[PositionSchema]
