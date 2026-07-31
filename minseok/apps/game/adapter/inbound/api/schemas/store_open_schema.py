from pydantic import BaseModel, Field


class OpenStoreRequestSchema(BaseModel):

    trdarCode: int = Field(description="상권 코드")
    serviceCode: str = Field(description="업종 코드 (예: CS100010)")
    budgetKrw: int = Field(gt=0, description="투입 자본 — 이 값이 가게 규모를 정한다")
    facilityScore: int = Field(10, ge=10, le=2000, description="시설 점수 — 10점당 좌석 1석")
    staffCount: int = Field(1, ge=0, le=20)
    priceFactor: float = Field(1.0, ge=0.6, le=1.3, description="가격 정책")

    model_config = {
        "json_schema_extra": {
            "example": {
                "trdarCode": 1001,
                "serviceCode": "CS100010",
                "budgetKrw": 3_000_000,
                "facilityScore": 300,
                "staffCount": 2,
                "priceFactor": 1.0,
            }
        }
    }


class OpenStoreReceiptSchema(BaseModel):

    storeId: int
    trdarName: str
    serviceName: str
    openedGameDay: int
    storeScale: float = Field(description="상권 평균 점포 대비 규모 (0.02~1.00)")
    fitness: float
    depositKrw: int = Field(description="보증금 — 폐업 시 회수된다")
    interiorKrw: int = Field(description="인테리어 — 회수되지 않는다")
    cashDeltaKrw: int
    cashKrw: int
    assumedMonthlyRentKrw: int = Field(description="게임 규칙으로 산정한 가정치")
