from pydantic import BaseModel, Field


class OpenStoreRequestSchema(BaseModel):

    trdarCode: int = Field(description="상권 코드")
    serviceCode: str = Field(description="업종 코드 (예: CS100010)")
    budgetKrw: int = Field(
        gt=0, description="투입 자본 — 규모와 시설 점수를 함께 정한다(시설은 수요에서 역산)"
    )
    staffCount: int = Field(1, ge=0, le=20)
    priceFactor: float = Field(1.0, ge=0.6, le=1.3, description="가격 정책")

    model_config = {
        "json_schema_extra": {
            "example": {
                "trdarCode": 1001,
                "serviceCode": "CS100010",
                "budgetKrw": 3_000_000,
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
    facilityScore: int = Field(description="투입 자본과 예상 수요에서 역산한 시설 점수")
    seatCount: int = Field(description="시설 점수 10점당 1석")
    dailyCapacityCustomers: int = Field(description="하루 수용 손님 — 착석·포장 구성 반영")
    takeoutRatio: float = Field(description="이 업종에서 좌석을 쓰지 않는 손님 비율(가정치)")
    fitness: float
    depositKrw: int = Field(description="보증금 — 폐업 시 회수된다")
    interiorKrw: int = Field(description="인테리어 — 회수되지 않는다")
    cashDeltaKrw: int
    cashKrw: int
    assumedMonthlyRentKrw: int = Field(description="게임 규칙으로 산정한 가정치")
