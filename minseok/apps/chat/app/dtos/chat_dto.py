from pydantic import BaseModel


class AreaStats(BaseModel):
    monthlyRevenueText: str
    revenueSourceText: str
    weekdayText: str
    storeCountText: str
    closureRateText: str
    openingRateText: str
    franchiseText: str
    footTrafficText: str
    topAgeText: str
    peakTimeText: str
    changeText: str
    operatingMonthsText: str
    dataSource: str
    hasRealData: bool


class AreaRecommendation(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    category: str        # 업종명 (표시용)
    serviceCode: str     # 업종 코드 — 지도 페이지가 같은 업종으로 상세/통계를 조회해야 한다
    reason: str
    stats: AreaStats


class StockCard(BaseModel):
    """주식 답변에 곁들이는 구조화 카드 데이터(프론트 렌더링용)."""

    symbol: str
    price: float
    direction: str        # UP | DOWN | NEUTRAL
    confidence: float
    rsi: float
    ma20: float
    ma50: float
    support: float
    resistance: float
    sentimentLabel: str
    headlines: list[str]
    atrPct: float = 0.0             # ATR(14)/종가 — 일 변동성 비율
    bbPercentB: float = 0.5         # 볼린저 %B (0=하단, 1=상단)
    volumeRatio: float = 1.0        # 최근 5일 평균 거래량 / 20일 평균
    obvSlope: float = 0.0           # OBV 20일 정규화 기울기 (수급 방향)
    momentum12To1: float = 0.0      # 12-1 모멘텀 (이력 부족 시 0.0)
    referenceUpSignal: bool = False # 백테스트 검증 통과 참고 신호 — 확률 아님
    # 결론 한 줄 — 서버가 verdict 로직으로 계산(페이지 히어로와 동일). 구버전 payload는 기본값.
    headline: str = ""              # 방향 결론 문장
    watch: str | None = None        # 지켜볼 포인트(관측 지시 — 조언 아님)
    strength: str = ""              # 신호 세기(약/보통/강) — 확신도% 오독 방지
    basis: str = ""                 # 결론의 근거 한 줄(표본·구간 또는 "표본 없음") — verdict detail
    value: list[str] = []           # 가치·체력 해석(펀더멘털) 대표 1~2줄 — 미수집이면 빈 리스트
    keywords: list[str] = []        # 영향 키워드 Top-N(B2, 헤드라인 빈도) — 표본 미달이면 빈 리스트


class NewsCardItem(BaseModel):
    """market_news 답변에 곁들이는 뉴스 근거 카드 1건(프론트 렌더링용)."""

    title: str
    publishedAt: str | None  # YYYY-MM-DD (발행일 미상이면 None)
    ticker: str | None       # 종목 무관 뉴스면 None
    sentiment: float | None  # -1 ~ +1 (라벨 없으면 None)
    eventType: str | None


class FinanceInputCard(BaseModel):
    key: str
    value: float
    source: str
    note: str


class FinanceCard(BaseModel):
    """재무 계산 카드 — 첫 줄(코드 작성)·입력값과 출처·핵심 수치. 다음 턴 승계 키이기도 하다."""

    trdarCode: int
    trdarName: str
    serviceCode: str
    serviceName: str
    headline: str
    assumptionNote: str
    inputs: list[FinanceInputCard]
    capex: int
    fundingGap: int
    bepMonthlySales: int
    attainment: float | None
    monthlyProfit: int | None
    runwayMonths: float | None
    rentLevel: str | None


class AskResponse(BaseModel):
    text: str
    recommendations: list[AreaRecommendation]
    conversationId: int
    stock: StockCard | None = None
    news: list[NewsCardItem] = []
    finance: FinanceCard | None = None
