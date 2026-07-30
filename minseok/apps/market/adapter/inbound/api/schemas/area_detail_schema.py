from __future__ import annotations

from datetime import date

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
    countByDay: dict[str, int] | None     # mon..sun — 요일별 객단가의 분모
    countByTime: dict[str, int] | None    # t00_06..t21_24
    countByGender: dict[str, int] | None  # male, female


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
    # 분포 — 평균값이 못 보는 '어떤 사람이 사는가'. 빈 구간은 0(결측 아님)
    priceBands: dict[str, int] | None  # under1b·b1·b2·b3·b4·b5·over6b
    areaBands: dict[str, int] | None   # under66·a66·a99·a132·a165


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
    monthlyAvgIncome: float | None  # 서울시가 2020년부터 제공 중단 — 최신 분기엔 항상 null
    totalExpenditure: float | None
    byCategory: list[SpendingCategorySchema]  # 금액 내림차순
    incomeBand: int | None        # 1~10
    incomePercentile: float | None  # 0~1 — 구간 숫자 대신 이걸 보여준다


class FloatingRhythmSchema(BaseModel):
    """통행 리듬 — 매출 리듬과 같은 축으로 대조해 구매 전환을 본다."""

    yearQuarter: int
    weekdayPop: int
    weekendPop: int
    malePop: int
    femalePop: int


class FacilitySchema(BaseModel):
    """집객시설 — '여기 사람이 왜 오는가'(외부 유입 앵커)."""

    yearQuarter: int
    total: int
    subwayStations: int
    busStops: int
    universities: int
    departmentStores: int
    hospitals: int
    # 성격 축 — 유입의 세기가 아니라 종류. 13종을 그대로 세지 않고 묶는다
    gateway: int      # 철도역·터미널·공항
    schools: int      # 유치원·초·중·고
    nightlife: int    # 극장·숙박
    convenience: int  # 은행·약국·슈퍼마켓·관공서


class ServiceRankSchema(BaseModel):
    code: str
    name: str
    monthlySales: int
    storeCount: int | None
    salesPerStore: int | None
    salesQoq: float | None
    closureRate: float | None


class PermitOpeningSchema(BaseModel):
    name: str
    category: str | None
    happenedOn: date


class PermitChurnSchema(BaseModel):
    """인허가 대장 기준 업소 교체 — 분기 팩트가 못 주는 '업소 단위·임의 기간' 축.

    active(영업중 수)는 상권분석서비스의 점포 수와 **출처도 집계 기준도 다르다** —
    같은 화면에서 비교하거나 검산하지 않는다.
    """

    months: int
    opened: int
    closed: int
    active: int
    recentOpenings: list[PermitOpeningSchema]
    recentClosings: list[PermitOpeningSchema]


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
    permitChurn: PermitChurnSchema | None
    serviceRanking: list[ServiceRankSchema]
    insights: list[InsightSchema]
