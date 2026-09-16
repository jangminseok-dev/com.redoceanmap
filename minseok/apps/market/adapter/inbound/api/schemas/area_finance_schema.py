from pydantic import BaseModel, Field


class SourcedValueSchema(BaseModel):
    key: str
    value: float
    source: str = Field(description="input | history | profile | area_avg | franchise | assumed | ecos")
    note: str


class StressSchema(BaseModel):
    rateDeltaPp: float
    loanRate: float
    monthlyProfit: int | None
    runwayMonths: float | None


class ScenarioSchema(BaseModel):
    key: str
    monthlySales: int
    monthlyProfit: int
    runwayMonths: float | None


class AreaFinanceResponse(BaseModel):
    """결정론 재무 계산 — 값마다 출처를 병기한다. 은행 상품 추천은 없다."""

    trdarCode: int
    trdarName: str
    districtName: str
    serviceCode: str
    serviceName: str
    headline: str
    assumptionNote: str
    inputs: list[SourcedValueSchema]
    capex: int
    fundingGap: int
    loan: int
    fixedMonthly: int
    bepMonthlySales: int
    attainment: float | None
    monthlyProfit: int | None
    cashAfter: int
    runwayMonths: float | None
    stress: list[StressSchema]
    scenarios: list[ScenarioSchema]
    rentQuarter: int | None = Field(description="임대료 기준 분기(R-ONE) — 미적재면 None")
    rentLevel: str | None = Field(description="area | zone | city")
