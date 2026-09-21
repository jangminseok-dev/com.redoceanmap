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
  basis?: string; // 결론의 근거 한 줄(표본·95% 구간). 구버전 히스토리 payload에는 없다
  value?: string[]; // 가치·체력 해석(펀더멘털) 대표 1~2줄 — 미수집이면 빈 배열
  keywords?: string[]; // 영향 키워드 Top-N(B2, 헤드라인 빈도 — 예측 아님). 표본 미달이면 빈 배열
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
  // 위험 신호(2026-09-21) — 신호 보드와 같은 판정. 결론 한 줄이 중립일 때 앞세운다. 봉이 모자라면 null
  risk?: {
    vol_state: "HIGH" | "NORMAL" | "LOW"; // 향후 20거래일 변동성 확대 가능성
    drawdown_risk: "HIGH" | "NORMAL" | "LOW"; // 20거래일 안 -10% 하락 가능성
    trend: "UP" | "DOWN" | "MIXED";
    rv20: number; // 최근 20일 실현 변동성(연율)
    rv_percentile: number; // 자기 1년 분포 안 위치(0~1)
    evidence: { key: RiskStat["key"]; test_rate: number; base_rate: number }[]; // 검증 통과한 실측만
  } | null;
  live?: boolean; // true = 미수집 종목 — yfinance 라이브 이력 기반 계산
  earnings_veto?: boolean; // true = 실적 발표 ±2일 — 신호를 관망으로 강등(SAVE 대조 편입 배지)
};

// ── GET /stock/{symbol}/quote ──

export type StockQuote = {
  symbol: string;
  price: number;
  delayed: boolean; // true = 지연 시세(yfinance 무료)
  previous_close?: number | null;
  change_pct?: number | null; // 전일 대비 (0.012 = +1.2%)
  fetched_at?: string | null; // 벤더 조회 시각(UTC ISO) — 구버전 응답 호환 옵셔널
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
  // 신호 근거·연속성(2026-09-17) — 역추세 신호라 "반등 후보인데 떨어지는 중"이 정상임을 보여준다
  rsi?: number | null;
  bb_percent_b?: number | null;
  signal_days?: number; // 같은 방향 신호 연속 일수(오늘 포함)
  since_signal_pct?: number | null; // 연속 신호 첫날 기준가 대비 최신가
  // 위험 신호(2026-09-17 재설계) — 봉이 모자라면 null
  rv20?: number | null; // 최근 20일 실현 변동성(연율, 0.35 = 35%)
  rv_percentile?: number | null; // 자기 1년 분포 안 위치(0~1)
  vol_state?: "HIGH" | "NORMAL" | "LOW" | null; // 향후 20거래일 변동성 확대 가능성
  trend?: "UP" | "DOWN" | "MIXED" | null;
  drawdown_risk?: "HIGH" | "NORMAL" | "LOW" | null; // 20거래일 안 -10% 하락 가능성
};

// 위험 신호 상태 하나의 검증 실측(최신 주간 리포트의 검증 구간)
export type RiskStat = {
  key: "vol_high" | "vol_low" | "drop_high" | "drop_low";
  label: string;
  outcome_label: string;
  side: "high" | "low";
  test_rate: number | null;
  base_rate: number | null;
  lift: number | null;
  n_eff: number;
  train_lift: number | null;
  validated: boolean;
};

export type StockBoard = {
  horizon_days: number;
  rows: StockBoardRow[];
  risk_stats?: RiskStat[];
  risk_report_ran_at?: string | null;
  risk_test_period?: string | null;
};

// ── GET /stock/{symbol}/prices ──

// 차트에서 관측된 형태. **예측이 아니다** — 어떤 형태가 그려져 있는지 알아본 결과이며
// 매매 판단을 대체하지 않는다.
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
  // 점수 v2(2026-09-17) — 향후 1년 폐업률을 가르는 3축. value·benchmark 단위: 폐업률 %, 영업 개월, 점포당 월매출 만원
  key: "closure_stability" | "persistence" | "sales_level";
  name: string;
  score: number; // 0~100 — 50이 서울 중앙 상권
  value: number;
  benchmark: number;
};

export type FitnessComponent = {
  key: "demand_match" | "hour_match" | "saturation" | "survival";
  label: string;
  score: number; // 0~1
  weight: number;
};

export type FitnessDiagnosis = {
  tone: "good" | "warn" | "bad";
  message: string;
};

// 입지 적합도 — /market/trdar/{code}/fitness. observed*는 실데이터, 가정치 필드는 없다
export type AreaFitness = {
  trdarCode: number;
  trdarName: string;
  serviceCode: string;
  serviceName: string;
  yearQuarter: number;
  observedMonthlySalesAmount: number;
  observedStoreCount: number;
  observedSimilarStoreCount: number;
  observedSalesPerStore: number;
  observedTicketPrice: number;
  observedClosureRate: number;
  observedOperatingMonthsAvg: number;
  totalScore: number; // 0~1
  components: FitnessComponent[];
  diagnoses: FitnessDiagnosis[];
  hasSales: boolean;
  hasStore: boolean;
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
  changeIndicatorName: string | null; // 상권변화지표(다이나믹/상권확장/상권축소/정체) — 결측이면 null
};

export type DongRollupRow = {
  districtName: string;
  dongName: string;
  areaCount: number;
  monthlySales: number | null;
  storeCount: number | null;
  salesPerStore: number | null;
  salesQoq: number | null; // 동 합계 기준 — 소속 상권 하나라도 직전 분기 결측이면 null
};

export type AreaRanking = {
  yearQuarter: number | null;
  rows: AreaRankingRow[];
  // 이 엔드포인트 자신의 필터 어휘(최신 분기에 실적 있는 업종)
  services: { code: string; name: string }[];
  dongRollup: DongRollupRow[]; // 행정동 롤업(I-3) — 필터 반영 부분집합의 서버 집계
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

// ── GET /market/areas/{code}/public · /market/areas/public-index (서버 컴포넌트 직접 호출) ──
// 비로그인 공개 페이지(A-4). 백엔드 AreaPublicView가 필드를 절제한다 — 여기서 늘리지 않는다.
export type AreaPublic = {
  trdarCode: number;
  trdarName: string;
  districtName: string;
  divisionName: string;
  yearQuarter: number | null;
  score: {
    total: number;
    grade: string; // 우수 / 양호 / 보통 / 주의 / 위험
    components: ScoreComponent[];
  } | null;
  serviceCode: string | null;
  serviceName: string | null;
  storeCount: number | null;
  salesPerStore: number | null; // 원/월
  salesQoq: number | null; // %
  closureRate: number | null; // %
  floatingPop: number | null; // 주중+주말 통행 인구
  insights: Insight[];
};

export type AreaIndexRow = {
  trdarCode: number;
  trdarName: string;
  districtName: string;
  divisionName: string;
};

// ── /stock/paper/* (직접 호출 — snake_case DTO) — AI 모의투자. 실제 매매 아님·권유 아님(기록 보고) ──
export type PaperRules = {
  rules_version?: string;
  assumed_initial_cash_krw: number;
  assumed_fee_rate: number;
  assumed_usdkrw: number; // 고정 환율 — 수집이 없어 상수
  assumed_max_position_weight: number;
  assumed_max_positions: number;
  assumed_signal_hold_sessions?: number;
  ai_fill?: string;
  user_fill?: string;
};

export type PaperBoardRow = {
  key: string; // exaone | signal
  kind: "exaone" | "signal";
  label: string;
  equity_krw: number;
  return_pct: number;
  open_positions: number;
  trades: number;
  last_as_of: string | null;
};

export type PaperBenchmarkPoint = { as_of: string; equity_krw: number };

export type PaperBoard = {
  rows: PaperBoardRow[];
  spy: PaperBenchmarkPoint[]; // 초기 자본을 SPY에 넣고 들고 있었을 때
  replay_until: string | null; // 이 날짜까지는 리플레이 구간
  rules: PaperRules;
};

export type PaperPosition = {
  ticker: string;
  name: string;
  side: "LONG" | "SHORT";
  quantity: number;
  avg_price: number; // 종목 통화
  last_price: number | null;
  unrealized_pct: number | null;
  value_krw: number;
  opened_at: string;
};

export type PaperEquityPoint = {
  as_of: string;
  cash_krw: number;
  positions_value_krw: number;
  equity_krw: number;
  replayed: boolean;
};

export type PaperTrade = {
  id: number;
  ticker: string;
  side: "LONG" | "SHORT";
  action: "BUY" | "SELL" | "SHORT" | "COVER";
  quantity: number;
  price: number;
  fee_krw: number;
  realized_pnl_krw: number | null;
  ts: string;
  decision_id: number | null;
  reason: string | null;
  evidence: { news_ids?: number[]; signals?: string[] } | null;
  replayed: boolean;
};

export type PaperAccount = {
  key: string;
  kind: "exaone" | "signal";
  label: string;
  cash_krw: number;
  equity_krw: number;
  initial_cash_krw: number;
  started_on: string;
  positions: PaperPosition[];
  equity: PaperEquityPoint[];
  trades: PaperTrade[];
};

export type PaperOrder = {
  ticker: string;
  action: "BUY" | "SELL" | "SHORT" | "COVER";
  weight: number;
  reason: string;
  cites: { news_ids: number[]; signals: string[] };
  reason_kind: "news" | "indicator" | "mixed" | "none";
};

export type PaperRejected = { ticker: string; action: string; reason: string };

export type PaperCandidateNews = {
  news_id: number;
  title: string;
  sentiment: number | null;
  event_type: string | null;
  published_on: string;
  url?: string;
};

export type PaperCandidate = {
  ticker: string;
  name: string;
  last_close: number;
  return_5d_pct: number | null;
  direction: "UP" | "DOWN" | "NEUTRAL" | "NONE";
  score: number | null;
  up_rate: number | null;
  baseline_up_rate: number | null;
  ready: boolean;
  atr_pct: number | null;
  regime: string | null;
  earnings_veto: boolean;
  sentiment_3d: number | null;
  news: PaperCandidateNews[];
};

export type PaperScore = {
  ticker: string;
  action: string;
  reason_kind: string;
  realized_return_pct: number;
  hit: boolean;
};

export type PaperDecision = {
  id: number;
  as_of: string;
  market_view: string;
  orders: PaperOrder[];
  rejected: PaperRejected[];
  candidates: PaperCandidate[];
  fills: PaperTrade[];
  scores: PaperScore[];
  replayed: boolean;
  latency_ms: number;
};

export type PaperDecisions = { key: string; decisions: PaperDecision[] }; // as_of 내림차순

export type PaperScoreBucket = {
  key: string;
  n: number;
  hits: number;
  hit_rate: number | null; // 표본이 min_samples 미만이면 null — 숫자를 노출하지 않는다
  ci_low: number | null;
  ci_high: number | null;
};

export type PaperScorecard = {
  key: string;
  total: PaperScoreBucket;
  by_reason: PaperScoreBucket[];
  by_action: PaperScoreBucket[];
  min_samples: number;
};

// ── /bookmarks (직접 호출 — snake_case DTO) ──
export type Bookmark = {
  id: number;
  target_type: "stock" | "area";
  target_key: string;
  label: string;
  created_at: string;
};

// ── GET /bookmarks/board (직접 호출 — snake_case DTO) — 관심 보드(③-M7) ──
export type BookmarkStockStatus = {
  ticker: string; // 실제 저장 티커 — 딥링크·통화 판별용
  as_of: string; // 신호 기준일(일일 동결 스냅샷)
  direction: "UP" | "DOWN" | "NEUTRAL";
  price: number; // 최신 수집 종가 — 준실시간 아님
  change_pct: number | null; // 전일 대비 비율(0.02 = +2%)
  ready: boolean; // 검증 참고 신호(통계적 유의) 여부
  price_as_of: string | null; // 가격 기준일 — 신호 기준일보다 최신일 수 있다
};

export type BookmarkAreaStatus = {
  total: number; // 종합점수(50점 = 서울 평균 수준)
  grade: string; // 우수 / 양호 / 보통 / 주의 / 위험
  sales_qoq_pct: number | null; // 매출 전분기 대비 — 이미 % 단위(3.2 = +3.2%)
  seoul_qoq_pct: number | null; // 점수 v2 이후 항상 null(서울 비교값 없음) — 호환 유지
};

export type BookmarkBoardItem = {
  id: number;
  target_type: "stock" | "area";
  target_key: string;
  label: string;
  created_at: string;
  stock: BookmarkStockStatus | null; // 상태 없으면 null(열화 — 목록은 항상 뜬다)
  area: BookmarkAreaStatus | null;
};

// ── /alert-settings (직접 호출 — snake_case DTO) — 관심 종목 이메일 알림 수신 설정 ──
export type AlertSetting = {
  email_alerts: boolean; // 미설정 회원은 백엔드가 true(기본 수신)로 응답
  telegram_chat_id: string | null; // 텔레그램 채널(I-7) — 미등록이면 null
};

// ── /price-alerts (직접 호출 — snake_case DTO) — 가격 도달 알림 조건([6], one-shot) ──
export type PriceAlert = {
  id: number;
  ticker: string;
  target_price: number;
  direction: "above" | "below";
  active: boolean; // 도달 통지 후 false — 재알림은 재등록
  triggered_at: string | null;
  created_at: string;
};

export type PriceAlertList = {
  alerts: PriceAlert[];
  max_active: number;
};

// ── /profile (직접 호출 — snake_case DTO) — 투자·창업 프로파일 설문(밴드 기반) ──
export type InvestorProfile = {
  purpose: "startup" | "invest" | "both";
  risk_level: 1 | 2 | 3 | 4 | 5;
  budget_band: "under_30m" | "30m_50m" | "50m_100m" | "100m_300m" | "over_300m";
  debt_burden: "none" | "manageable" | "heavy";
  horizon: "short" | "mid" | "long";
  updated_at: string;
};
