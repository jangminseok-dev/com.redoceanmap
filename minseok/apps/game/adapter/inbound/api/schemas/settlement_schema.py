from pydantic import BaseModel, Field


class AdviceSchema(BaseModel):

    tone: str = Field(description="good | warn | bad")
    message: str


class SettlementSchema(BaseModel):
    """분기 결산 1건. simulated_*는 시뮬레이션, assumed_*는 게임 규칙 가정치다."""

    storeId: int
    trdarName: str
    serviceName: str
    gameQuarter: int
    daysCounted: int
    simulatedSalesKrw: int
    assumedRentKrw: int
    assumedLaborKrw: int
    assumedCogsKrw: int
    assumedUtilityKrw: int
    profitKrw: int
    customerCount: int
    averageTurnedAwayRatio: float
    performanceRatio: float = Field(
        description="내 매출 ÷ 상권 평균 점포가 같은 규모였을 때의 매출"
    )
    advices: list[AdviceSchema]


class SettlementListResponseSchema(BaseModel):

    settlements: list[SettlementSchema]
    newlySettled: int = Field(description="이번 호출에서 새로 확정된 분기 수")
    totalProfitKrw: int
    gameDay: int
    gameQuarter: int
    seasonOver: bool
