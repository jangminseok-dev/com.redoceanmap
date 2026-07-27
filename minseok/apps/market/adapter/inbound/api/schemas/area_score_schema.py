from __future__ import annotations

from pydantic import BaseModel


class ScoreComponentSchema(BaseModel):
    key: str  # sales_growth / floating_growth / store_health / persistence
    name: str
    score: float  # 0~100 — 50이 시도 벤치마크 동률
    value: float
    benchmark: float


class AreaScoreSchema(BaseModel):
    total: float  # 가용 컴포넌트 단순 평균
    grade: str  # 우수 / 양호 / 보통 / 주의 / 위험
    components: list[ScoreComponentSchema]


class TrendPointSchema(BaseModel):
    yearQuarter: int  # 예: 20254
    monthlySales: int | None
    salesQoq: float | None  # 직전 분기 대비 %
    totalFloatingPop: int | None
    floatingQoq: float | None
    salesYoy: float | None
    floatingYoy: float | None


class AreaScoreResponse(BaseModel):
    trdarCode: int
    trdarName: str
    districtName: str
    score: AreaScoreSchema | None  # 산출 근거 팩트가 전혀 없으면 null
    trend: list[TrendPointSchema]  # yearQuarter 오름차순
