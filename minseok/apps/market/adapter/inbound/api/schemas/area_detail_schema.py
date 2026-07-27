from __future__ import annotations

from pydantic import BaseModel


class SalesMixSchema(BaseModel):
    yearQuarter: int
    weekdayAmount: int
    weekendAmount: int
    byDay: dict[str, int]     # mon..sun
    byTime: dict[str, int]    # t00_06..t21_24
    byGender: dict[str, int]  # male, female
    byAge: dict[str, int]     # age10..age60Plus
    monthlyCount: int
    monthlyAmount: int        # 객단가(금액÷건수)의 분모와 짝
    # 건수 축 — 금액만으론 '많이 오는 층'과 '비싸게 쓰는 층'이 구분되지 않는다
    weekdayCount: int
    weekendCount: int
    countByAge: dict[str, int] | None


class AgeBandSchema(BaseModel):
    band: str  # "10".."60+"
    male: int
    female: int


class PopulationSchema(BaseModel):
    yearQuarter: int
    total: int
    byAge: list[AgeBandSchema]


class HouseholdsSchema(BaseModel):
    total: int
    apartment: int


class ApartmentSchema(BaseModel):
    yearQuarter: int
    complexCount: int
    avgPrice: int  # 원
    avgArea: int   # ㎡


class DemandSchema(BaseModel):
    resident: PopulationSchema | None
    working: PopulationSchema | None
    households: HouseholdsSchema | None
    apartment: ApartmentSchema | None


class SpendingCategorySchema(BaseModel):
    key: str
    label: str
    amount: float  # 원


class SpendingSchema(BaseModel):
    yearQuarter: int
    monthlyAvgIncome: float | None
    totalExpenditure: float | None
    byCategory: list[SpendingCategorySchema]  # 금액 내림차순


class FloatingRhythmSchema(BaseModel):
    """통행 리듬 — 매출 리듬과 같은 축으로 대조해 구매 전환을 본다."""

    yearQuarter: int
    weekdayPop: int
    weekendPop: int


class FacilitySchema(BaseModel):
    """집객시설 — '여기 사람이 왜 오는가'(외부 유입 앵커)."""

    yearQuarter: int
    total: int
    subwayStations: int
    busStops: int
    universities: int
    departmentStores: int
    hospitals: int


class InsightSchema(BaseModel):
    key: str
    tone: str  # positive | neutral | warning
    text: str


class AreaDetailResponse(BaseModel):
    trdarCode: int
    trdarName: str
    districtName: str
    serviceCode: str | None  # 매출 팩트가 없는 상권이면 null
    serviceName: str | None
    salesMix: SalesMixSchema | None
    demand: DemandSchema | None
    spending: SpendingSchema | None
    floating: FloatingRhythmSchema | None
    facility: FacilitySchema | None
    insights: list[InsightSchema]
