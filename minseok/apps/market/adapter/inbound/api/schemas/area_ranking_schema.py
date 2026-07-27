from pydantic import BaseModel


class AreaRankingRowSchema(BaseModel):
    trdarCode: int
    trdarName: str
    districtName: str
    dongName: str
    divisionCode: str
    divisionName: str
    lat: float
    lng: float
    monthlySales: int | None
    storeCount: int | None
    salesPerStore: int | None
    salesQoq: float | None
    closureRate: float | None
    areaSize: float | None


class ServiceOptionSchema(BaseModel):
    code: str
    name: str


class AreaRankingResponse(BaseModel):
    yearQuarter: int | None
    rows: list[AreaRankingRowSchema]
    services: list[ServiceOptionSchema]
