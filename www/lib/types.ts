// 백엔드 계약 타입 모음 — 채팅 응답(AskResponse)과 조회 API 응답의 단일 정의처.

// ── 채팅 응답: 상권 추천 카드 (AreaStats는 서버가 문장으로 포맷한 텍스트 계약) ──

export type AreaStats = {
  // 수익성 (공공데이터 실계산)
  monthlyRevenueText: string;
  revenueSourceText: string;
  weekdayText: string;
  // 점포 현황
  storeCountText: string;
  closureRateText: string;
  openingRateText: string;
  franchiseText: string;
  // 유동인구
  footTrafficText: string;
  topAgeText: string;
  peakTimeText: string;
  // 상권 변화
  changeText: string;
  operatingMonthsText: string;
  // 메타
  dataSource: string;
  hasRealData: boolean;
};

export type Area = {
  id: string; // trdar_code — /market/trdar/{id}/stats 조회 키
  name: string;
  lat: number;
  lng: number;
  category: string;   // 업종명(표시용)
  serviceCode?: string; // 업종 코드 — 지도 상세/통계를 같은 업종으로 조회하기 위한 키
  reason: string;
  stats: AreaStats;
};

// ── 채팅 응답: 종목 카드 ──

export type StockAnalysis = {
  symbol: string;
  price: number;
  direction: "UP" | "DOWN" | "NEUTRAL";
  confidence: number;
  rsi: number;
  ma20: number;
  ma50: number;
  support: number;
  resistance: number;
  sentimentLabel: string;
  headlines: string[];
  atrPct?: number;
  bbPercentB?: number;
  volumeRatio?: number;
  obvSlope?: number;
  momentum12To1?: number;
  referenceUpSignal?: boolean;
  // 서버가 verdict 로직으로 계산한 결론 — 페이지 히어로와 동일(구버전 payload엔 없음)
  headline?: string;
  watch?: string | null;
  strength?: string; // 신호 세기(약/보통/강)
  value?: string[]; // 가치·체력 해석(펀더멘털) 대표 1~2줄 — 미수집이면 빈 배열
};

// ── POST /stock/analyze (직접 호출 — snake_case DTO) ──

export type SignalContribution = {
  key: "sentiment" | "rsi" | "trend" | "bollinger" | "obv" | "momentum";
  signal: number; // -1 ~ 1 원신호
  weight: number;
  contribution: number; // signal × weight
};

export type StockAnalyzeResult = {
  symbol: string;
  price: number;
  direction: "UP" | "DOWN" | "NEUTRAL";
  confidence: number;
  sentiment: number;
  sentiment_label: string;
  rsi: number;
  ma20: number;
  ma50: number;
  support: number;
  resistance: number;
  headlines: string[];
  atr_pct: number;
  bb_percent_b: number;
  volume_ratio: number;
  obv_slope: number;
  momentum_12_1: number;
  reference_up_signal: boolean;
  // 신규 필드 — 구버전 응답 호환을 위해 옵셔널
  score?: number; // 가중 합산 종합 점수 (-1~1)
  up_threshold?: number;
  down_threshold?: number;
  neutral_reason?: "atr_veto" | "volume_confirm" | null;
  signals?: SignalContribution[];
  insights?: Insight[];
  // 최근 30일 뉴스 라벨 평균. null이면 기준선 표본 부족 → 감성이 절대값으로 신호에 들어간다
  sentiment_baseline?: number | null;
  sentiment_surprise?: number | null; // 당일 − 기준선 (실제 신호에 투입된 값)
};

// ── GET /stock/{symbol}/forecast ──

export type StockForecast = {
  symbol: string;
  resolved_ticker: string;
  as_of: string;
  base_price: number;
  horizon_days: number;
  signal_direction: "UP" | "DOWN" | "NEUTRAL"; // 지표 신호 기준(감성 미반영)
  probability: {
    up_rate: number;
    sample_size: number;
    hits: number;
    ci_low: number; // Wilson 95%
    ci_high: number;
    baseline_up_rate: number;
    ready: boolean; // n≥100 + 하한 > 기준선
  } | null;
  band: {
    source: "quantile" | "atr";
    q25_pct: number; // horizon일 뒤 수익률 (-0.011 = -1.1%)
    median_pct: number;
    q75_pct: number;
  } | null;
  insights: Insight[];
  // 현재 국면 — 예측이 아니라 "지금까지 얼마나 떨어져 있나". 신규 필드라 옵셔널
  position?: {
    rsi: number;
    rsi_zone: "oversold" | "neutral" | "overbought";
    drawdown_from_high_pct: number; // 60일 고점 대비 (-0.124 = -12.4%)
    above_support_pct: number; // 60일 저점 대비 여력
    atr_pct: number;
  } | null;
  // 하방 리스크 실측 — signal_direction에 DOWN은 오지 않는다(하락 방향 미검증)
  downside?: {
    trough_median_pct: number | null; // 구간 내 장중 최대 낙폭 중앙값
    trough_q25_pct: number | null; // 하위 25% = 더 나쁜 쪽
    down_close_rate: number | null;
    dip_samples: number; // 낙폭이 있었던 표본 — 회복률의 분모
    recovery_rate: number | null;
    recovery_days_median: number | null;
  } | null;
  live?: boolean; // true = 미수집 종목 — yfinance 라이브 이력 기반 계산
};

// ── GET /stock/{symbol}/quote ──

export type StockQuote = {
  symbol: string;
  price: number;
  delayed: boolean; // true = 지연 시세(yfinance 무료)
  previous_close?: number | null;
  change_pct?: number | null; // 전일 대비 (0.012 = +1.2%)
};

// ── GET /stock/board ──

export type StockBoardRow = {
  ticker: string;
  name: string; // 표시용 한글명 — 모르는 티커는 티커 그대로
  as_of: string;
  direction: "UP" | "DOWN" | "NEUTRAL";
  score: number; // -1 ~ 1
  price: number; // 최신 수집 종가 — 준실시간 아님
  change_pct: number | null;
  up_rate: number | null;
  baseline_up_rate: number | null;
  edge_pct: number | null; // up_rate − baseline
  ready: boolean;
  sparkline: number[]; // 최근 종가(과거 → 최신)
  price_as_of: string | null; // 가격 기준일 — 신호 기준일(as_of)과 다를 수 있다
  volume?: number | null; // 마지막 봉 거래량(주) — 구버전 응답 호환을 위해 옵셔널
  turnover?: number | null; // 거래대금 = 종가 × 거래량. 통화는 종목을 따른다(원/달러 혼재)
};

export type StockBoard = {
  horizon_days: number;
  rows: StockBoardRow[];
};

// ── GET /stock/{symbol}/prices ──

// 차트에서 관측된 형태. **예측이 아니다** — 어떤 형태가 그려져 있는지 알아본 결과이며
// 매매 판단을 대체하지 않는다(게임 쪽 GameChartPattern과 같은 백엔드 알고리즘).
export type ChartPattern = {
  name: string; // head_and_shoulders 등 기계용 식별자
  label: string;
  startIndex: number; // bars 배열 위치
  endIndex: number;
  confidence: number; // 기하학적 근접도(0~1) — 적중 확률이 아니다
  points: [number, number][]; // (bars 인덱스, 종가) — 인덱스 오름차순
  note: string;
};

export type PriceBar = {
  ts: string; // 봉 시작(UTC ISO)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type PriceHistory = {
  symbol: string;
  resolvedTicker: string;
  timeframe: "1d" | "5m";
  bars: PriceBar[]; // ts 오름차순
  live?: boolean; // true = 미수집 종목 — yfinance 라이브 이력 폴백
  patterns?: ChartPattern[]; // 종가 곡선에서 관측된 형태(신뢰도 상위) — 구버전 응답 호환
};

// ── GET /stock/{symbol}/news ──

export type StockNewsItem = {
  id: number;
  title: string;
  source: string;
  url: string;
  publishedAt: string | null;
  sentiment: number | null; // -1 ~ +1
  eventType: string | null;
  confidence: number | null;
};

// ── GET /stock/{symbol}/fundamentals ──

export type FundamentalSnapshot = {
  asOf: string;
  source: "yfinance" | "dart";
  per: number | null;
  pbr: number | null;
  roe: number | null;
  debtToEquity: number | null;
  fcf: number | null;
  marketCap: number | null;
  eps: number | null;
  bps: number | null;
};

export type Fundamentals = {
  symbol: string;
  snapshots: FundamentalSnapshot[];
  insights?: Insight[]; // 규칙 기반 해석(dart 우선 병합)
};

// ── GET /market/trdar/{code}/stats ──

export type QuarterStat = {
  yearQuarter: number; // 예: 20244
  monthlySales: number | null;
  weekdaySales: number | null;
  storeCount: number | null;
  openingRate: number | null;
  closureRate: number | null;
  franchiseCount: number | null;
  totalFloatingPop: number | null;
  // 율(%)만으론 소규모 상권에서 오독한다("3개 중 1개 폐업 = 33%")
  similarIndustryCount: number | null;
  openingCount: number | null;
  closureCount: number | null;
};

export type AreaStatsDetail = {
  trdarCode: number;
  trdarName: string;
  districtName: string;
  serviceCode: string | null;
  serviceName: string | null;
  series: QuarterStat[]; // yearQuarter 오름차순
  latest: {
    floatingByAge: {
      age10: number; age20: number; age30: number;
      age40: number; age50: number; age60Plus: number;
    } | null;
    floatingByTime: {
      t00_06: number; t06_11: number; t11_14: number;
      t14_17: number; t17_21: number; t21_24: number;
    } | null;
    changeIndicator: string | null;
    operatingMonthsAvg: number | null;
    regionOperatingMonthsAvg: number | null;
    closureMonthsAvg: number | null;
    regionClosureMonthsAvg: number | null;
  };
};

// ── GET /market/trdar/{code}/score ──

export type ScoreComponent = {
  key: "sales_growth" | "floating_growth" | "store_health" | "persistence";
  name: string;
  score: number; // 0~100 — 50이 시도 벤치마크 동률
  value: number;
  benchmark: number;
};

export type AreaScoreDetail = {
  trdarCode: number;
  trdarName: string;
  districtName: string;
  score: {
    total: number;
    grade: string; // 우수 / 양호 / 보통 / 주의 / 위험
    components: ScoreComponent[];
  } | null;
  trend: {
    yearQuarter: number;
    monthlySales: number | null;
    salesQoq: number | null; // 직전 분기 대비 %
    totalFloatingPop: number | null;
    floatingQoq: number | null;
    // 전년 동분기 대비 — 계절성이 큰 분기 데이터에서 QoQ보다 정직하다
    salesYoy: number | null;
    floatingYoy: number | null;
  }[];
};

// ── GET /market/trdar/{code}/detail ──

export type Insight = {
  key: string;
  tone: "positive" | "neutral" | "warning";
  text: string;
};

export type AgeBandRow = { band: string; male: number; female: number };

// 인허가 대장의 개업(또는 폐업) 업소 한 건 — 상호가 붙어야 "무엇이 열렸나"가 읽힌다
export type PermitOpening = {
  name: string;
  category: string | null; // 업태(한식·커피숍 등)
  happenedOn: string; // ISO date
};

export type AreaDetail = {
  trdarCode: number;
  trdarName: string;
  districtName: string;
  serviceCode: string | null;
  serviceName: string | null;
  salesMix: {
    yearQuarter: number;
    weekdayAmount: number;
    weekendAmount: number;
    byDay: Record<string, number>; // mon..sun
    byTime: Record<string, number>; // t00_06..t21_24
    byGender: { male: number; female: number };
    byAge: Record<string, number>; // age10..age60Plus
    monthlyCount: number;
    monthlyAmount: number;
    // 건수 축 — 금액÷건수로 "언제 누가 얼마씩 쓰는가"(객단가)를 낸다
    weekdayCount: number;
    weekendCount: number;
    countByAge: Record<string, number> | null;
    countByDay: Record<string, number> | null; // 요일별 객단가의 분모
    countByTime: Record<string, number> | null;
    countByGender: Record<string, number> | null;
  } | null;
  demand: {
    resident: { yearQuarter: number; total: number; byAge: AgeBandRow[] } | null;
    working: { yearQuarter: number; total: number; byAge: AgeBandRow[] } | null;
    households: { total: number; apartment: number } | null;
    apartment: {
      yearQuarter: number;
      complexCount: number;
      avgPrice: number; // 원
      avgArea: number; // ㎡
      // 분포 — 평균값이 못 보는 '어떤 사람이 사는가'. 빈 구간은 0(결측 아님)
      priceBands: Record<string, number> | null; // under1b·b1·b2·b3·b4·b5·over6b
      areaBands: Record<string, number> | null; // under66·a66·a99·a132·a165
    } | null;
  } | null;
  spending: {
    yearQuarter: number;
    monthlyAvgIncome: number | null; // 원 — 서울시가 2020년부터 제공 중단, 최신 분기엔 항상 null
    totalExpenditure: number | null; // 원
    byCategory: { key: string; label: string; amount: number }[]; // 금액 내림차순
    incomeBand: number | null; // 1~10
    incomePercentile: number | null; // 0~1 — 구간 숫자 대신 이걸 보여준다
  } | null;
  // 통행 리듬 — 매출 리듬과 같은 축으로 대조하면 구매 전환이 보인다
  floating: {
    yearQuarter: number;
    weekdayPop: number;
    weekendPop: number;
    malePop: number;
    femalePop: number;
  } | null;
  // 집객시설 — "여기 사람이 왜 오는가"
  facility: {
    yearQuarter: number;
    total: number;
    subwayStations: number;
    busStops: number;
    universities: number;
    departmentStores: number;
    hospitals: number;
    // 성격 축 — 유입의 세기가 아니라 종류
    gateway: number; // 철도역·터미널·공항
    schools: number; // 유치원·초·중·고
    nightlife: number; // 극장·숙박
    convenience: number; // 은행·약국·슈퍼마켓·관공서
  } | null;
  // 인허가 대장 기준 업소 교체 — "요즘 여기 뭐가 새로 열었나"
  // active(영업중 수)는 상권분석서비스의 점포 수와 출처·집계 기준이 달라 함께 비교하지 않는다.
  permitChurn: {
    months: number;
    opened: number;
    closed: number;
    active: number;
    recentOpenings: PermitOpening[];
    recentClosings: PermitOpening[];
  } | null;
  // 상권 안 업종 랭킹 — "이 자리에서 뭐가 되나"
  serviceRanking: {
    code: string;
    name: string;
    monthlySales: number;
    storeCount: number | null;
    salesPerStore: number | null;
    salesQoq: number | null;
    closureRate: number | null;
  }[];
  insights: Insight[];
};

// ── 채팅 응답: market_news 뉴스 근거 카드 ──

export type NewsCardItem = {
  title: string;
  publishedAt: string | null; // YYYY-MM-DD
  ticker: string | null;
  sentiment: number | null; // -1 ~ +1
  eventType: string | null;
};

// ── GET /chat/conversations ──

export type ConversationSummary = {
  id: number;
  title: string;
  createdAt: string;
  // 마지막 카드 요약(2026-08-17) — 목록의 도메인 필터·재개 라벨. 구버전 응답 호환 옵셔널
  domain?: "stock" | "market" | null;
  label?: string | null; // 종목 심볼 또는 "첫 상권 이름 외 N곳"
};

export type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
  payload: { recommendations?: Area[]; stock?: StockAnalysis; news?: NewsCardItem[] } | null;
  createdAt: string;
};

// ── GET /recommendations ──

export type RecommendationItem = {
  id: number;
  conversation_id: number;
  trdar_code: number;
  trdar_name: string;
  district_name: string;
  category: string;
  reason: string;
  lat: number;
  lng: number;
  created_at: string;
};

// ── GET /market/areas ──

export type MarketArea = {
  trdar_code: number;
  trdar_name: string;
  trdar_div_code: string;
  trdar_div_name: string;
  lat: number;
  lng: number;
  district_name: string;
  adm_dong_name: string;
  area_size: number;
  region: string;
};

// ── GET /market/areas/ranking ──

export type AreaRankingRow = {
  trdarCode: number;
  trdarName: string;
  districtName: string;
  dongName: string;
  divisionCode: string;
  divisionName: string;
  lat: number;
  lng: number;
  monthlySales: number | null;
  storeCount: number | null;
  salesPerStore: number | null;
  salesQoq: number | null;
  closureRate: number | null;
  areaSize: number | null; // ㎡ — 밀도 정규화용(절대량 비교의 규모 착시 제거)
};

export type AreaRanking = {
  yearQuarter: number | null;
  rows: AreaRankingRow[];
  // 이 엔드포인트 자신의 필터 어휘(최신 분기에 실적 있는 업종)
  services: { code: string; name: string }[];
};

// 쇼케이스 — 비로그인 첫 화면. 랭킹과 달리 필드가 6개뿐이다(공개 응답이라 의도적으로 줄였다).
export type AreaShowcaseRow = {
  trdarCode: number;
  trdarName: string;
  districtName: string;
  divisionName: string;
  salesPerStore: number;
  storeCount: number;
};

// 상위 카드의 극단값(1위가 점포당 19.6억)을 읽는 자 — 유형별 중앙값
export type DivisionMedian = {
  divisionName: string;
  areaCount: number;
  medianSalesPerStore: number;
};

export type AreaShowcase = {
  yearQuarter: number | null;
  quarterFrom: number | null;
  areaCount: number;
  minStoreCount: number; // 컷오프 — 카피가 숫자를 하드코딩하지 않게 서버가 실어 보낸다
  rows: AreaShowcaseRow[];
  divisionMedians: DivisionMedian[];
};

// --- GET /game/myself · /game/market/prices ---------------------------------
// 게임 시각은 서버가 계산한다 — 프론트는 틱을 만들지도, 가격을 계산하지도 않는다
// (게임 상태는 시각의 함수이고 그 함수는 서버에만 있다 — game-harness §1-6).

export type GameRulebook = {
  id: number;
  name: string;
  introduction: string;
  epochId: number; // 바뀌면 이전 시즌 기록은 읽기 전용
  ruleVersion: string;
  tick: number; // 1틱 = 60초
  gameDay: number;
  gameQuarter: number; // 1~8
  dayOfQuarter: number; // 1~90
  seasonOver: boolean;
  ticksRemaining: number;
  // 매매 규칙 — 서버가 실어 보낸다. 프론트가 수수료율을 하드코딩하지 않는다.
  initialCashKrw: number;
  reservedCashKrw: number;
  feeRate: number;
  shortCarryRatePerGameDay: number;
  ticksPerGameDay: number;
  // 레버리지 규칙 — 프론트가 배율·청산선·만료를 하드코딩하지 않는다(구버전 응답 호환)
  leverageTiers?: number[];
  maintenanceMarginRatio?: number;
  leveragedExpiryTicks?: number;
  maxLeveragedPositions?: number;
};

export type GamePosition = {
  id: number;
  symbol: string;
  name: string;
  sector: string;
  side: "LONG" | "SHORT";
  quantity: number;
  entryTick: number;
  entryPriceKrw: number;
  currentPriceKrw: number;
  marketValueKrw: number; // 지금 청산하면 돌아올 금액(수수료·보유비용 반영)
  leverage: number;
  liquidationPriceKrw: number | null; // 이 가격에 닿으면 강제청산. 1배는 청산되지 않아 null
  expiresTick: number | null; // 레버리지 포지션의 자동 마감 시점
  unrealizedPnlKrw: number;
  unrealizedPct: number;
};

// 유저가 직접 청산하지 않은 마감 — 미접속 중에 일어난 일이다
export type GameClosedNotice = {
  id: number;
  symbol: string;
  name: string;
  side: "LONG" | "SHORT";
  quantity: number;
  leverage: number;
  closedGameDay: number;
  exitPriceKrw: number;
  realizedPnlKrw: number;
  reason: "liquidated" | "expired" | "settled";
};

export type GameWallet = {
  cashKrw: number;
  investableKrw: number; // 최소 생활자금을 뺀 투자 가능액
  reservedKrw: number;
  positionValueKrw: number;
  totalAssetKrw: number;
  initialCashKrw: number;
  totalReturnPct: number;
  epochId: number;
  ruleVersion: string;
  tick: number;
  gameDay: number;
  gameQuarter: number;
  seasonOver: boolean;
  positions: GamePosition[];
  recentlyClosed?: GameClosedNotice[]; // 미접속 중 강제청산·만료된 포지션(구버전 응답 호환)
};

// 창업 — observed_*는 서울시 상권분석서비스 실데이터, assumed_*는 게임 규칙 산출값,
// simulated_*는 규칙 + 결정론 난수. 접두사가 곧 출처다.

export type GameFitnessComponent = {
  key: "demand_match" | "hour_match" | "saturation" | "survival";
  label: string;
  score: number; // 0.0~1.0
  weight: number;
};

export type GameDiagnosis = {
  tone: "good" | "warn" | "bad";
  message: string;
};

export type GameAreaFitness = {
  trdarCode: number;
  trdarName: string;
  serviceCode: string;
  serviceName: string;
  observedQuarter: number;
  observedMonthlySalesAmount: number;
  observedStoreCount: number;
  observedSimilarStoreCount: number;
  observedSalesPerStore: number;
  observedTicketPrice: number;
  observedClosureRate: number;
  observedOperatingMonthsAvg: number;
  fitness: number; // 0.4~1.6
  totalScore: number;
  components: GameFitnessComponent[];
  simulatedMonthlySalesKrw: number;
  diagnoses: GameDiagnosis[];
  hasSales: boolean;
  hasStore: boolean;
  openable: boolean; // 창업 가능 여부 — 매출 기록이 없으면 false
  assumedMinimumCapitalKrw: number; // 창업이 거절되지 않는 최소 자본(0 = 창업 불가)
  assumedViableCapitalKrw: number; // 손님이 하루 1명은 오는 자본 — 이보다 적으면 개점휴업
};

export type GameOpenStoreReceipt = {
  storeId: number;
  trdarName: string;
  serviceName: string;
  openedGameDay: number;
  storeScale: number;
  facilityScore: number;
  seatCount: number;
  dailyCapacityCustomers: number;
  takeoutRatio: number;
  fitness: number;
  depositKrw: number;
  interiorKrw: number;
  cashDeltaKrw: number;
  cashKrw: number;
  assumedMonthlyRentKrw: number;
};

export type GameStoreSummary = {
  storeId: number;
  trdarName: string;
  serviceName: string;
  status: string;
  openedGameDay: number;
  daysOpen: number;
  storeScale: number;
  fitness: number;
  cumulativeSalesKrw: number;
  cumulativeProfitKrw: number;
};

export type GameDailyRow = {
  gameDay: number;
  simulatedSalesKrw: number;
  simulatedCustomerCount: number;
  capacityCustomerCount: number;
  turnedAwayRatio: number;
  assumedRentKrw: number;
  assumedLaborKrw: number;
  assumedCogsKrw: number;
  assumedUtilityKrw: number;
  profitKrw: number;
};

export type GameCustomerBucket = {
  label: string;
  count: number;
};

export type GameStoreDaily = {
  storeId: number;
  trdarName: string;
  serviceName: string;
  status: string;
  openedGameDay: number;
  daysOpen: number;
  storeScale: number;
  fitness: number;
  seats: number;
  depositKrw: number;
  interiorKrw: number;
  priceFactor: number; // 지금 유효한 운영 결정 — 조정 폼의 기본값
  staffCount: number;
  facilityScore: number;
  observedSalesPerStore: number;
  observedTicketPrice: number;
  assumedMonthlyRentKrw: number;
  cumulativeSalesKrw: number;
  cumulativeProfitKrw: number;
  averageTurnedAwayRatio: number;
  rows: GameDailyRow[];
  customersByAge: GameCustomerBucket[];
  customersByHour: GameCustomerBucket[];
  customersByTaste: GameCustomerBucket[];
  tick: number;
  gameDay: number;
  gameQuarter: number;
  seasonOver: boolean;
};

// ── POST /game/stores/{id}/decisions · /close ──
export type GameStoreDecisionReceipt = {
  storeId: number;
  effectiveFromDay: number; // 오늘 다음 날 — 확정된 과거는 바뀌지 않는다
  priceFactor: number;
  staffCount: number;
  facilityScore: number;
  facilityAdded: number;
  interiorCostKrw: number; // 시설 추가투자분 — 회수 불가
  cashDeltaKrw: number;
  cashKrw: number;
};

export type GameCloseStoreReceipt = {
  storeId: number;
  closedGameDay: number;
  depositRefundKrw: number;
  interiorLostKrw: number;
  cashDeltaKrw: number;
  cashKrw: number;
  pendingSettlement: boolean; // 폐업일이 낀 분기 손익은 결산 조회 때 확정된다
};

export type GameAdvice = {
  tone: "good" | "warn" | "bad";
  message: string;
};

export type GameSettlement = {
  storeId: number;
  trdarName: string;
  serviceName: string;
  gameQuarter: number;
  daysCounted: number;
  simulatedSalesKrw: number;
  assumedRentKrw: number;
  assumedLaborKrw: number;
  assumedCogsKrw: number;
  assumedUtilityKrw: number;
  profitKrw: number;
  customerCount: number;
  averageTurnedAwayRatio: number;
  performanceRatio: number; // 내 매출 ÷ 상권 평균 점포가 같은 규모였을 때의 매출
  advices: GameAdvice[];
};

export type GameSettlementList = {
  settlements: GameSettlement[];
  newlySettled: number; // 이번 조회에서 새로 확정된 분기 수
  totalProfitKrw: number;
  gameDay: number;
  gameQuarter: number;
  seasonOver: boolean;
};

export type GameTradeReceipt = {
  leverage: number;
  liquidationPriceKrw: number | null;
  expiresTick: number | null;
  positionId: number;
  symbol: string;
  name: string;
  side: "LONG" | "SHORT";
  quantity: number;
  priceKrw: number; // 체결가 — 요청이 도착한 틱의 가격
  feeKrw: number;
  carryKrw: number;
  cashDeltaKrw: number;
  realizedPnlKrw: number | null; // 청산에만
  cashKrw: number;
  tick: number;
};

// 지정가 주문 — 진입 예약(ENTRY)과 청산 예약(EXIT, 익절·손절)이 한 테이블을 쓴다.
// `trigger`는 "이 방향으로 닿으면 체결": le=지정가 이하, ge=지정가 이상.
export type GameLimitOrder = {
  id: number;
  kind: "ENTRY" | "EXIT";
  symbol: string;
  name: string;
  side: "LONG" | "SHORT";
  positionId: number | null; // EXIT만 — 어느 포지션의 예약인가
  trigger: "le" | "ge";
  limitPriceKrw: number;
  quantity: number;
  leverage: number;
  placedTick: number;
  expiresTick: number; // 만료는 체결 스캔 범위를 묶는 성능 장치라 없앨 수 없다(연장만 가능)
  status: "pending" | "filled" | "cancelled" | "expired";
  filledTick: number | null;
  filledPriceKrw: number | null;
  reservedCashKrw: number; // ENTRY가 묶어둔 현금 — 취소·만료 시 돌아온다
};

// `settledCount`는 **이번 조회에서** 확정된 건수다 — 조회가 곧 체결 판정 시점이라(cron 0개)
// 폴링 응답에서 0보다 크면 그 사이에 체결·만료가 일어난 것이다.
export type GameOrderList = {
  tick: number;
  pending: GameLimitOrder[];
  recent: GameLimitOrder[];
  settledCount: number;
};

export type GameOrderReceipt = {
  orders: GameLimitOrder[];
  cashKrw: number;
};

export type GamePricePoint = {
  tick: number;
  priceKrw: number;
};

export type GameSymbolPrices = {
  symbol: string;
  name: string; // 가상 회사명 — 실재 기업이 아니다
  sector: string; // 업종은 실제 시장에서 가져왔다
  sectorGroup: string; // 묶음 업종 — 섹터 이벤트가 걸리는 단위이자 화면 필터 축
  meme: boolean; // 밈 종목 — 변동성이 크고 전용 뉴스가 붙는다
  priceKrw: number;
  changePct: number; // 게임 1일(현실 1시간) 전 대비
  series: GamePricePoint[];
};

export type GameMarketEvent = {
  tick: number;
  scope: "symbol" | "sector" | "market";
  target: string;
  targetName: string;
  positive: boolean;
  headline: string; // 템플릿 문구 — 가상 회사 대상이며 LLM 생성이 아니다
  affectedSymbols: string[]; // 이 뉴스가 실제로 가격을 미는 종목 코드들
  expectedImpactPct: number; // 설계된 즉시 충격(%)
  remainingImpactPct: number; // 현재 틱에 남아 있는 기여(%) — 0에 가까우면 영향 소멸
};

export type GameMarketPrices = {
  virtual: boolean; // 항상 true — 실시세가 아니라 서버가 생성한 가상 주가
  calibrated: boolean; // false면 변동성이 실데이터 캘리브레이션 전 잠정값
  epochId: number;
  ruleVersion: string;
  tick: number;
  gameDay: number;
  gameQuarter: number;
  seasonOver: boolean;
  symbols: GameSymbolPrices[];
  events: GameMarketEvent[]; // 최근 호재·악재(최신순)
  candles: GameCandle[]; // candle_symbol 지정 시에만. 마지막 봉은 진행 중일 수 있다
  symbolInfo: GameSymbolInfo | null; // candle_symbol 지정 시에만
  patterns: GameChartPattern[]; // 〃 — 선택 종목의 틱 곡선에서 관측된 형태
  movingAverages: GameMovingAverage[]; // 〃 — 봉 배열과 인덱스가 맞는다
  rsi: (number | null)[]; // 〃 — RSI(14), 봉 배열과 인덱스가 맞는다
  analysis: GameSymbolAnalysis | null; // 〃 — 현재 상태 요약(예측 아님)
  orderBook: GameOrderBook | null; // 〃 — 호가창·VI·공매도 잔고
};

export type GameQuote = { priceKrw: number; assumedQuantity: number };

// 주문장을 저장하지 않고 시각의 함수로 만든다 — 잔량은 유동성 모형이 낸 가정치다.
export type GameOrderBook = {
  bids: GameQuote[]; // 높은 가격부터
  asks: GameQuote[]; // 낮은 가격부터
  spreadKrw: number;
  tickSizeKrw: number;
  halted: boolean; // 변동성 완화장치(VI) 발동 중 — 매매가 잠긴다
  limitState: "upper" | "lower" | "none";
  shortInterestPct: number;
};

// 상태 분해 한 축. 부호 규약: **양수 = 뜨겁다**(많이 올랐다·과매수·거래 몰림·호재).
export type GameSignalAxis = {
  key: "trend" | "momentum" | "position" | "flow" | "news";
  label: string;
  value: number; // -1.0 ~ 1.0
  weight: number;
  note: string; // 해석 문장 — 예측이 아니다
};

// ⚠️ 예측이 아니다. 게임 주가는 브라운 운동 + 뉴스 충격이라 과거 형태에 미래 정보가 없다.
// 점수가 높다고 오를 확률이 높다는 뜻이 아니며, 화면 문구도 이 구분을 지켜야 한다.
export type GameSymbolAnalysis = {
  score: number; // -1.0 ~ 1.0
  label: string; // 과열 | 달아오름 | 잠잠 | 식는 중 | 침체
  axes: GameSignalAxis[];
  rsi: number | null;
  percentB: number | null;
  atrPct: number | null;
  volumeRatio: number | null;
  obvSlope: number | null;
  newsImpactPct: number; // 창 안 뉴스가 지금 가격에 넣고 있는 값(%)
  headlineCount: number;
  dailyPatterns: GameChartPattern[]; // 일봉 축에서 관측된 형태(좌표는 봉 인덱스)
};

// 관측된 형태일 뿐 예측이 아니다. 게임 주가는 브라운 운동+이벤트로 생성되므로
// 이 형태에는 시장 심리가 담겨 있지 않다 — 화면 문구에서도 이 구분을 지킨다.
export type GameChartPattern = {
  name: string; // head_and_shoulders 등 기계용 식별자
  label: string;
  startIndex: number; // series 배열 위치
  endIndex: number;
  confidence: number; // 기하학적 근접도(0~1) — 적중 확률이 아니다
  points: [number, number][]; // (series 인덱스, 가격 원)
  note: string; // 통상적 해석 — 매매 지시나 예측이 아니다
};

export type GameCandle = {
  gameDay: number;
  openKrw: number;
  highKrw: number;
  lowKrw: number;
  closeKrw: number;
  simulatedVolume: number; // 게임 규칙 산출값 — 게임에 호가·체결이 없어 실제 거래량이 아니다
};

// 이동평균선 하나. points는 봉 배열과 **같은 길이·같은 순서**이고,
// 표본이 모자란 앞 구간은 null이다(0으로 채우면 바닥에서 치솟는 가짜 선이 그려진다).
export type GameMovingAverage = {
  period: number; // 게임일
  points: (number | null)[];
};

// 실적 지표(PER·ROE 등)는 게임에 그 개념이 없어 백엔드가 내려주지 않는다 — 지어내지 않는다
export type GameSymbolInfo = {
  symbol: string;
  name: string;
  sector: string;
  sectorGroup: string;
  meme: boolean;
  basePriceKrw: number; // 시즌 시작가
  gameDailySigmaPct: number; // 게임 1일 변동성(%) — 체감 배수 적용값
  recentHighKrw: number;
  recentLowKrw: number;
  recentDays: number;
  // 어닝(§13-3) — 전부 가정치이며 실재 기업의 재무가 아니다.
  // 실적은 가격과 **독립으로** 생성되고 PER·PBR은 둘의 비율이라, 많이 오르면 PER이 오른다.
  gameQuarter: number;
  assumedSharesOutstanding: number;
  assumedEpsKrw: number; // 연환산 주당순이익. 음수면 적자
  assumedBpsKrw: number;
  assumedRoe: number;
  assumedDebtRatio: number;
  assumedNetIncomeKrw: number;
  assumedMarketCapKrw: number;
  per: number | null; // 적자면 null — 음수 PER을 만들지 않는다
  pbr: number | null;
  earningsSurprise: "beat" | "miss" | "inline";
};

// 지수 선물 게임은 2026-08-04 폐지 — GameFutures* 타입과 /game/futures 호출을 제거했다.
// 백엔드 futures 슬라이스와 game_positions.instrument 컬럼도 같은 날 제거됐다(양쪽 완료).
