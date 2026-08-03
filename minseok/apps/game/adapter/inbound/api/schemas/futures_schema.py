from pydantic import BaseModel, Field


class IndexPointSchema(BaseModel):
    tick: int
    point: int


class FuturesPositionSchema(BaseModel):
    id: int
    contractCode: str
    side: str = Field(description="LONG | SHORT")
    contracts: int
    entryPriceKrw: int = Field(description="1계약 진입 금액")
    currentPriceKrw: int
    marketValueKrw: int = Field(description="지금 청산하면 돌아올 금액")
    unrealizedPnlKrw: int
    unrealizedPct: float
    expiresTick: int
    ticksToExpiry: int


class FuturesMarketResponse(BaseModel):
    virtual: bool = Field(description="항상 true — 서버가 생성한 가상 지수다")
    contractCode: str
    expiryTick: int
    ticksToExpiry: int
    indexPoint: int = Field(description="현물 지수 — 12종목 상대가격의 기하평균 × 1000")
    futuresPoint: int
    basisPct: float = Field(description="(선물 − 현물) ÷ 현물. 양수면 콘탱고")
    contractValueKrw: int = Field(description="1계약 명목 금액")
    marginPerContractKrw: int
    multiplierKrw: int
    marginRatio: float
    maxContracts: int
    series: list[IndexPointSchema]
    positions: list[FuturesPositionSchema]
    investableKrw: int
    tick: int
    gameDay: int
    gameQuarter: int
    seasonOver: bool


class OpenFuturesRequest(BaseModel):
    side: str = Field(description="LONG | SHORT")
    contracts: int = Field(gt=0, description="계약 수")

    model_config = {"json_schema_extra": {"example": {"side": "LONG", "contracts": 2}}}


class FuturesReceiptSchema(BaseModel):
    positionId: int
    contractCode: str
    side: str
    contracts: int
    priceKrw: int = Field(description="1계약 체결 금액")
    futuresPoint: int
    feeKrw: int
    marginKrw: int
    cashDeltaKrw: int
    realizedPnlKrw: int | None
    cashKrw: int
    expiresTick: int
    tick: int


class FuturesMyselfResponse(BaseModel):
    id: str
    name: str
    introduction: str
    endpoints: list[str]
    constraints: list[str]
