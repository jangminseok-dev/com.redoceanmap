from pydantic import BaseModel, Field


class StoreDecisionRequest(BaseModel):
    """가격·직원·시설 변경. 넣지 않은 항목은 직전 결정을 그대로 잇는다."""

    priceFactor: float | None = Field(None, description="0.6~1.3. 높이면 객단가↑ 손님↓")
    staffCount: int | None = Field(None, description="0~20명. 다음 날부터 인건비에 반영된다")
    facilityScore: int | None = Field(
        None, description="증가만 가능 — 인테리어비는 회수되지 않는다"
    )


class StoreDecisionResponse(BaseModel):

    storeId: int
    effectiveFromDay: int = Field(
        description="적용 시작 게임일 — 오늘 다음 날이다. 확정된 과거는 바뀌지 않는다"
    )
    priceFactor: float
    staffCount: int
    facilityScore: int
    facilityAdded: int
    interiorCostKrw: int = Field(description="시설 추가투자분 — 회수 불가")
    cashDeltaKrw: int
    cashKrw: int


class CloseStoreResponse(BaseModel):

    storeId: int
    closedGameDay: int
    depositRefundKrw: int = Field(description="보증금은 전액 회수된다")
    interiorLostKrw: int = Field(description="인테리어는 회수되지 않는다")
    cashDeltaKrw: int
    cashKrw: int
    pendingSettlement: bool = Field(
        description="폐업일이 낀 분기의 손익이 남아 있다. 결산 조회 시 확정된다"
    )


class StoreActionMyselfResponse(BaseModel):

    id: str
    name: str
    introduction: str
    endpoints: list[str]
    constraints: list[str]
