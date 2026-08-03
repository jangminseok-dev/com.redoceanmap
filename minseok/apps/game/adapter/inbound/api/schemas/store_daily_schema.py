from pydantic import BaseModel, Field


class DailyRowSchema(BaseModel):

    gameDay: int
    simulatedSalesKrw: int
    simulatedCustomerCount: int
    capacityCustomerCount: int = Field(description="시설이 받을 수 있었던 최대 손님 수")
    turnedAwayRatio: float = Field(description="자리가 없어 돌아간 비율")
    assumedRentKrw: int
    assumedLaborKrw: int
    assumedCogsKrw: int
    assumedUtilityKrw: int
    profitKrw: int


class CustomerBucketSchema(BaseModel):

    label: str
    count: int


class StoreSummarySchema(BaseModel):

    storeId: int
    trdarName: str
    serviceName: str
    status: str
    openedGameDay: int
    daysOpen: int
    storeScale: float
    fitness: float
    cumulativeSalesKrw: int
    cumulativeProfitKrw: int


class StoreDailyResponseSchema(BaseModel):
    """observed_*는 실데이터, assumed_*는 게임 규칙, simulated_*는 규칙+결정론 난수."""

    storeId: int
    trdarName: str
    serviceName: str
    status: str
    openedGameDay: int
    daysOpen: int
    storeScale: float
    fitness: float
    seats: int
    depositKrw: int
    interiorKrw: int
    priceFactor: float
    staffCount: int
    facilityScore: int

    observedSalesPerStore: int
    observedTicketPrice: int
    assumedMonthlyRentKrw: int

    cumulativeSalesKrw: int
    cumulativeProfitKrw: int
    averageTurnedAwayRatio: float

    rows: list[DailyRowSchema]
    customersByAge: list[CustomerBucketSchema]
    customersByHour: list[CustomerBucketSchema]
    customersByTaste: list[CustomerBucketSchema]

    tick: int
    gameDay: int
    gameQuarter: int
    seasonOver: bool
