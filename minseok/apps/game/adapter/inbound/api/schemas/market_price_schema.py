from pydantic import BaseModel, Field


class PricePointSchema(BaseModel):

    tick: int
    priceKrw: int


class SymbolPricesSchema(BaseModel):

    symbol: str
    name: str = Field(description="가상 회사명 — 실재 기업이 아니다")
    sector: str = Field(description="업종은 실제 시장에서 가져왔다")
    sectorGroup: str = Field(description="묶음 업종 — 섹터 이벤트가 걸리는 단위")
    meme: bool = Field(description="밈 종목 — 변동성이 크고 전용 뉴스가 붙는다")
    priceKrw: int
    changePct: float = Field(description="게임 1일(현실 1시간) 전 대비 등락률")
    series: list[PricePointSchema]


class CandleSchema(BaseModel):

    gameDay: int
    openKrw: int
    highKrw: int
    lowKrw: int
    closeKrw: int


class ChartPatternSchema(BaseModel):

    name: str = Field(description="head_and_shoulders 등 기계용 식별자")
    label: str
    startIndex: int = Field(description="series 배열 위치")
    endIndex: int
    confidence: float = Field(
        description="이상적 형태와의 기하학적 근접도(0~1) — 적중 확률이 아니다"
    )
    points: list[tuple[int, int]] = Field(description="(series 인덱스, 가격 원)")
    note: str = Field(description="통상적 해석 — 매매 지시나 예측이 아니다")


class SymbolInfoSchema(BaseModel):

    symbol: str
    name: str
    sector: str
    sectorGroup: str
    meme: bool = Field(description="밈 종목 — σ 배수가 적용된 변동성이다")
    basePriceKrw: int = Field(description="시즌 시작가")
    gameDailySigmaPct: float = Field(description="게임 1일 변동성(%) — 체감 배수 적용값")
    recentHighKrw: int
    recentLowKrw: int
    recentDays: int = Field(description="고저가를 잰 게임일 수")


class MarketEventSchema(BaseModel):

    tick: int
    scope: str = Field(description="symbol | sector | market")
    target: str
    targetName: str
    positive: bool
    headline: str = Field(description="템플릿 문구 — 가상 회사 대상이며 LLM 생성이 아니다")
    affectedSymbols: list[str] = Field(
        description="이 뉴스가 실제로 가격을 미는 종목 코드들"
    )
    expectedImpactPct: float = Field(description="설계된 즉시 충격(%)")
    remainingImpactPct: float = Field(
        description="현재 틱에 남아 있는 기여(%) — 0에 가까우면 영향이 소멸했다"
    )


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
    candles: list[CandleSchema] = Field(
        description="candle_symbol을 지정했을 때만 채워진다. 마지막 봉은 진행 중일 수 있다"
    )
    symbolInfo: SymbolInfoSchema | None = Field(
        description="candle_symbol을 지정했을 때만. 실적 지표(PER 등)는 게임에 개념이 없어 넣지 않는다"
    )
    patterns: list[ChartPatternSchema] = Field(
        description=(
            "선택 종목의 틱 곡선에서 관측된 형태(신뢰도 상위). 예측이 아니며, "
            "게임 주가는 브라운 운동+이벤트로 생성되므로 시장 심리가 담겨 있지 않다"
        )
    )
