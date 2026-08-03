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
    leverage: int = 1
    liquidationPriceKrw: int | None = Field(
        None, description="이 가격에 닿으면 강제청산. 1배는 청산되지 않아 null"
    )
    expiresTick: int | None = Field(None, description="레버리지 포지션의 자동 마감 시점")


class ClosedNoticeSchema(BaseModel):
    """유저가 직접 청산하지 않은 마감 — 미접속 중에 일어난 일이다."""

    id: int
    symbol: str
    name: str
    side: str
    quantity: int
    leverage: int
    closedGameDay: int
    exitPriceKrw: int
    realizedPnlKrw: int
    reason: str = Field(description="liquidated | expired | settled")


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
    recentlyClosed: list[ClosedNoticeSchema] = Field(
        default=[], description="미접속 중 강제청산·만료된 포지션(최근 5건)"
    )
