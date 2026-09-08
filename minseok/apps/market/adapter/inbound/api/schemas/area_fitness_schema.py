from pydantic import BaseModel, Field


class FitnessComponentSchema(BaseModel):
    key: str = Field(description="demand_match | hour_match | saturation | survival")
    label: str
    score: float = Field(description="0.0~1.0")
    weight: float


class DiagnosisSchema(BaseModel):
    tone: str = Field(description="good | warn | bad")
    message: str


class AreaFitnessResponse(BaseModel):
    """observed*는 서울시 상권분석서비스 실데이터다. 창업비용·임대료 같은 가정치는 없다."""

    trdarCode: int
    trdarName: str
    serviceCode: str
    serviceName: str
    yearQuarter: int = Field(description="기준 실데이터 분기 — 최신 적재 분기")

    observedMonthlySalesAmount: int
    observedStoreCount: int
    observedSimilarStoreCount: int
    observedSalesPerStore: int = Field(description="점포당 월매출")
    observedTicketPrice: int = Field(description="객단가 = 매출액 ÷ 매출건수")
    observedClosureRate: float
    observedOperatingMonthsAvg: float

    totalScore: float = Field(description="4축 가중 합 0.0~1.0")
    components: list[FitnessComponentSchema]
    diagnoses: list[DiagnosisSchema]
    hasSales: bool
    hasStore: bool
