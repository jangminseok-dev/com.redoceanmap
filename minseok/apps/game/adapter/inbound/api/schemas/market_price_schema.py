from pydantic import BaseModel, Field


class PricePointSchema(BaseModel):

    tick: int
    priceKrw: int


class SymbolPricesSchema(BaseModel):

    symbol: str
    name: str = Field(description="가상 회사명 — 실재 기업이 아니다")
    sector: str = Field(description="업종은 실제 시장에서 가져왔다")
    priceKrw: int
    changePct: float = Field(description="게임 1일(현실 1시간) 전 대비 등락률")
    series: list[PricePointSchema]


class MarketEventSchema(BaseModel):

    tick: int
    scope: str = Field(description="symbol | sector | market")
    target: str
    targetName: str
    positive: bool
    headline: str = Field(description="템플릿 문구 — 가상 회사 대상이며 LLM 생성이 아니다")


class MarketPricesResponseSchema(BaseModel):

    virtual: bool = Field(description="항상 true — 실시세가 아니라 서버가 생성한 가상 주가")
    calibrated: bool = Field(
        description="false면 종목 변동성이 실데이터 캘리브레이션 전 잠정값"
    )
    epochId: int
    ruleVersion: str
    tick: int
    gameDay: int
    gameQuarter: int
    seasonOver: bool
    symbols: list[SymbolPricesSchema]
    events: list[MarketEventSchema]
