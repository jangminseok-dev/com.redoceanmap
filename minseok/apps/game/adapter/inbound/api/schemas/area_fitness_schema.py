from pydantic import BaseModel, Field


class FitnessComponentSchema(BaseModel):

    key: str = Field(description="demand_match | hour_match | saturation | survival")
    label: str
    score: float = Field(description="0.0~1.0")
    weight: float


class DiagnosisSchema(BaseModel):

    tone: str = Field(description="good | warn | bad")
    message: str


class AreaFitnessResponseSchema(BaseModel):
    """observed_*는 서울시 상권분석서비스 실데이터, simulated_*는 게임 규칙 산출값이다."""

    trdarCode: int
    trdarName: str
    serviceCode: str
    serviceName: str
    observedQuarter: int = Field(description="기준 실데이터 분기 — 시즌 내내 고정")

    observedMonthlySalesAmount: int
    observedStoreCount: int
    observedSimilarStoreCount: int
    observedSalesPerStore: int = Field(description="점포당 월매출 — 매출 산식의 기준선")
    observedTicketPrice: int = Field(description="객단가 = 매출액 ÷ 매출건수")
    observedClosureRate: float
    observedOperatingMonthsAvg: float

    fitness: float = Field(description="0.4~1.6 — 매출에 곱해지는 적합도 계수")
    totalScore: float
    components: list[FitnessComponentSchema]
    simulatedMonthlySalesKrw: int = Field(
        description="점포당 기대매출 × 적합도 (인지도·시설 반영 전 게임 규칙 산출값)"
    )

    diagnoses: list[DiagnosisSchema]
    hasSales: bool
    hasStore: bool
