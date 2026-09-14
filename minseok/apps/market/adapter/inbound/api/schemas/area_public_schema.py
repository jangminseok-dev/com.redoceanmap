from pydantic import BaseModel


class PublicScoreComponentSchema(BaseModel):
    key: str
    name: str
    score: float
    value: float
    benchmark: float


class PublicScoreSchema(BaseModel):
    total: float
    grade: str  # 우수 / 양호 / 보통 / 주의 / 위험
    components: list[PublicScoreComponentSchema]


class PublicInsightSchema(BaseModel):
    key: str
    tone: str  # positive | neutral | warning
    text: str


class AreaPublicResponse(BaseModel):
    """비로그인에게 나가는 응답 — 필드를 늘리려면 AreaPublicView의 제외 사유를 먼저 읽는다."""

    trdarCode: int
    trdarName: str
    districtName: str
    divisionName: str
    yearQuarter: int | None
    score: PublicScoreSchema | None
    serviceCode: str | None
    serviceName: str | None
    storeCount: int | None
    salesPerStore: int | None
    salesQoq: float | None
    closureRate: float | None
    floatingPop: int | None
    insights: list[PublicInsightSchema]


class AreaIndexRowSchema(BaseModel):
    trdarCode: int
    trdarName: str
    districtName: str
    divisionName: str


class AreaIndexResponse(BaseModel):
    rows: list[AreaIndexRowSchema]
