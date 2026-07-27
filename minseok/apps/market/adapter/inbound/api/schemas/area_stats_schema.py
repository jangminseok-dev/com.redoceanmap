from __future__ import annotations

from pydantic import BaseModel


class QuarterStatSchema(BaseModel):
    yearQuarter: int  # 예: 20244
    monthlySales: int | None
    weekdaySales: int | None
    storeCount: int | None
    openingRate: float | None
    closureRate: float | None
    franchiseCount: int | None
    similarIndustryCount: int | None
    openingCount: int | None
    closureCount: int | None
    totalFloatingPop: int | None


class FloatingByAgeSchema(BaseModel):
    age10: int
    age20: int
    age30: int
    age40: int
    age50: int
    age60Plus: int


class FloatingByTimeSchema(BaseModel):
    t00_06: int
    t06_11: int
    t11_14: int
    t14_17: int
    t17_21: int
    t21_24: int


class AreaStatsLatestSchema(BaseModel):
    floatingByAge: FloatingByAgeSchema | None
    floatingByTime: FloatingByTimeSchema | None
    changeIndicator: str | None
    operatingMonthsAvg: float | None
    regionOperatingMonthsAvg: float | None
    closureMonthsAvg: float | None
    regionClosureMonthsAvg: float | None


class AreaStatsResponse(BaseModel):
    trdarCode: int
    trdarName: str
    districtName: str
    serviceCode: str | None  # 매출/점포 팩트가 없는 상권이면 null
    serviceName: str | None
    series: list[QuarterStatSchema]  # yearQuarter 오름차순
    latest: AreaStatsLatestSchema
