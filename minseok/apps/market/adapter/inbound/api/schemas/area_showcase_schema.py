from pydantic import BaseModel


class AreaShowcaseRowSchema(BaseModel):
    trdarCode: int
    trdarName: str
    districtName: str
    divisionName: str
    salesPerStore: int
    storeCount: int


class DivisionMedianSchema(BaseModel):
    divisionName: str
    areaCount: int
    medianSalesPerStore: int


class AreaShowcaseResponse(BaseModel):
    """비로그인에게도 나가는 응답 — 필드를 늘릴 때는 공개해도 되는지 먼저 따진다."""

    yearQuarter: int | None
    quarterFrom: int | None
    areaCount: int
    minStoreCount: int
    rows: list[AreaShowcaseRowSchema]
    divisionMedians: list[DivisionMedianSchema]
