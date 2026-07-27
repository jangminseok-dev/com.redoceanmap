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
};

export type StockBoard = {
  horizon_days: number;
  rows: StockBoardRow[];
};

// ── GET /stock/{symbol}/prices ──

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
    } | null;
  } | null;
  spending: {
    yearQuarter: number;
    monthlyAvgIncome: number | null; // 원
    totalExpenditure: number | null; // 원
    byCategory: { key: string; label: string; amount: number }[]; // 금액 내림차순
  } | null;
  // 통행 리듬 — 매출 리듬과 같은 축으로 대조하면 구매 전환이 보인다
  floating: { yearQuarter: number; weekdayPop: number; weekendPop: number } | null;
  // 집객시설 — "여기 사람이 왜 오는가"
  facility: {
    yearQuarter: number;
    total: number;
    subwayStations: number;
    busStops: number;
    universities: number;
    departmentStores: number;
    hospitals: number;
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
