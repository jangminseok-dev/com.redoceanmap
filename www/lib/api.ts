import type {
  AreaDetail,
  AreaRanking,
  Bookmark,
  AreaScoreDetail,
  AreaShowcase,
  AreaStatsDetail,
  ConversationMessage,
  ConversationSummary,
  Fundamentals,
  GameAreaFitness,
  GameMarketPrices,
  GameOpenStoreReceipt,
  GameRulebook,
  GameSettlementList,
  GameCloseStoreReceipt,
  GameStoreDaily,
  GameStoreDecisionReceipt,
  GameStoreSummary,
  GameOrderList,
  GameOrderReceipt,
  GameTradeReceipt,
  GameWallet,
  InvestorProfile,
  AlertSetting,
  BookmarkBoardItem,
  MarketArea,
  PriceHistory,
  RecommendationItem,
  StockAnalyzeResult,
  StockBoard,
  StockForecast,
  StockNewsItem,
  StockQuote,
} from "./types";

// 모든 GET 조회는 next.config rewrites(/api/backend/* → FastAPI)를 경유한다.
async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`/api/backend${path}`);  // 세션은 httpOnly 쿠키 — 자동 동행
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? "요청에 실패했습니다.");
  }
  return res.json();
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// 조회형 POST(부작용 없음) — react-query useQuery로 소비한다.
export const fetchStockAnalysis = async (symbol: string): Promise<StockAnalyzeResult> => {
  const res = await fetch(
    `/api/backend/stock/analyze?symbol=${encodeURIComponent(symbol)}`,
    { method: "POST" },
  );
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? "분석에 실패했습니다.");
  }
  return res.json();
};

export const fetchPriceHistory = (
  symbol: string,
  timeframe: "1d" | "5m",
  limit = 500,
): Promise<PriceHistory> =>
  getJson(`/stock/${encodeURIComponent(symbol)}/prices?timeframe=${timeframe}&limit=${limit}`);

export const fetchStockNews = (symbol: string, limit = 20): Promise<StockNewsItem[]> =>
  getJson(`/stock/${encodeURIComponent(symbol)}/news?limit=${limit}`);

export const fetchFundamentals = (symbol: string): Promise<Fundamentals> =>
  getJson(`/stock/${encodeURIComponent(symbol)}/fundamentals`);

export const fetchStockForecast = (symbol: string): Promise<StockForecast> =>
  getJson(`/stock/${encodeURIComponent(symbol)}/forecast`);

export const fetchStockQuote = (symbol: string): Promise<StockQuote> =>
  getJson(`/stock/${encodeURIComponent(symbol)}/quote`);

// 워치리스트 신호 보드 — 종목별 analyze/forecast를 N번 부르지 않고 축적 스냅샷을 한 번에 읽는다
export const fetchStockBoard = (horizon = 5, limit = 40): Promise<StockBoard> =>
  getJson(`/stock/board?horizon=${horizon}&limit=${limit}`);

// 업종을 넘기지 않으면 백엔드가 "매출 최대 업종"으로 폴백한다 — 사용자가 물은 업종과
// 다른 업종의 수치가 화면 전체에 깔리므로 채팅이 고른 업종 코드를 반드시 함께 보낸다.
const withService = (path: string, serviceCode?: string) =>
  serviceCode ? `${path}${path.includes("?") ? "&" : "?"}service_code=${encodeURIComponent(serviceCode)}` : path;

// quarters 기본 8 — 백엔드와 같은 값. 20분기까지 요청할 수 있다(매출·점포 보유 한도).
export const fetchAreaStats = (
  trdarCode: string | number,
  serviceCode?: string,
  quarters = 8,
): Promise<AreaStatsDetail> =>
  getJson(withService(`/market/trdar/${trdarCode}/stats?quarters=${quarters}`, serviceCode));

export const fetchAreaScore = (
  trdarCode: string | number,
  quarters = 8,
): Promise<AreaScoreDetail> =>
  getJson(`/market/trdar/${trdarCode}/score?quarters=${quarters}`);

export const fetchAreaInfo = (trdarCode: string | number): Promise<MarketArea> =>
  getJson(`/market/trdar/${trdarCode}/area`);

export const fetchAreaDetail = (
  trdarCode: string | number,
  serviceCode?: string,
): Promise<AreaDetail> =>
  getJson(withService(`/market/trdar/${trdarCode}/detail`, serviceCode));

export const fetchConversations = (limit = 30): Promise<ConversationSummary[]> =>
  getJson(`/chat/conversations?limit=${limit}`);

export const fetchConversationMessages = (id: number): Promise<ConversationMessage[]> =>
  getJson(`/chat/conversations/${id}/messages`);

export const fetchRecommendations = (limit = 8): Promise<RecommendationItem[]> =>
  getJson(`/recommendations?limit=${limit}`);

// 상권 디렉터리 — 1,650행을 한 번에 받고 정렬·검색은 클라이언트가 한다
// (admin/areas 선례. 왕복보다 useMemo 필터가 빠르다).
export const fetchAreaRanking = (params: {
  gu?: string;
  division?: string;
  serviceCode?: string;
}): Promise<AreaRanking> => {
  const qs = new URLSearchParams();
  if (params.gu) qs.set("gu", params.gu);
  if (params.division) qs.set("division", params.division);
  if (params.serviceCode) qs.set("service_code", params.serviceCode);
  const suffix = qs.toString() ? `?${qs}` : "";
  return getJson<AreaRanking>(`/market/areas/ranking${suffix}`);
};

// 첫 화면 쇼케이스 — 이 앱에서 로그인 없이 열리는 유일한 조회다(자치구별 점포당 매출 1위).
export const fetchAreaShowcase = (): Promise<AreaShowcase> =>
  getJson(`/market/areas/showcase`);

// 게임 — 규칙 안내 + 현재 게임 시각. 화면 진입 시 한 번 부른다.
export const fetchGameRulebook = (): Promise<GameRulebook> => getJson(`/game/myself`);

// 게임 시세 — 가격은 서버가 틱마다 계산한다(저장하지 않는다).
// 같은 틱을 다시 물으면 같은 값이라 폴링이 안전하다.
// candleSymbol을 넘기면 그 종목의 일봉과 종목 카드가 함께 온다.
// 한 종목만 받는 이유는 비용이다 — 하루당 60틱을 훑으므로 전 종목이면 응답 목표를 넘긴다.
export const fetchGamePrices = (
  ticks = 120,
  candleSymbol?: string,
  candleDays = 7,
): Promise<GameMarketPrices> => {
  const params = new URLSearchParams({ ticks: String(ticks) });
  if (candleSymbol) {
    params.set("candle_symbol", candleSymbol);
    params.set("candle_days", String(candleDays));
  }
  return getJson(`/game/market/prices?${params.toString()}`);
};

export const fetchGameWallet = (): Promise<GameWallet> => getJson(`/game/wallet`);

// 매매 — 체결가는 요청이 도착한 틱의 가격이다(예약 주문·지연 체결 없음).
async function postGame<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/backend${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? "요청에 실패했습니다.");
  }
  return res.json();
}

// leverage 2배 이상은 만료(게임 3일)와 강제청산이 붙는다 — 규칙은 /game/myself가 내려준다.
export const openGameTrade = (
  symbol: string,
  side: "LONG" | "SHORT",
  quantity: number,
  leverage = 1,
): Promise<GameTradeReceipt> => postGame(`/game/trades`, { symbol, side, quantity, leverage });

export const closeGameTrade = (positionId: number): Promise<GameTradeReceipt> =>
  postGame(`/game/trades/${positionId}/close`);

// 지정가 주문 — cron이 없다. **이 조회가 곧 체결 판정 시점이다**(지연 실행):
// 서버가 placed~min(now, expires) 구간을 훑어 확정하고 그 결과를 돌려준다.
// 그래서 폴링을 멈추면 체결도 멈춘 것처럼 보인다 — 화면이 열려 있는 동안 계속 부른다.
export const fetchGameOrders = (): Promise<GameOrderList> => getJson(`/game/orders`);

// 진입 예약 — 서버가 체결에 쓸 현금을 지금 묶는다(취소·만료 시 반환).
export const placeGameEntryOrder = (body: {
  symbol: string;
  side: "LONG" | "SHORT";
  quantity: number;
  limitPriceKrw: number;
  leverage: number;
}): Promise<GameOrderReceipt> => postGame(`/game/orders`, body);

// 익절·손절 — 둘 다 넣으면 OCO 한 쌍이 되어 한쪽이 체결되면 나머지가 취소된다.
// 같은 포지션에 다시 걸면 기존 예약을 갈아끼운다(서버 규칙).
export const placeGameExitOrder = (body: {
  positionId: number;
  takeProfitKrw: number | null;
  stopLossKrw: number | null;
}): Promise<GameOrderReceipt> => postGame(`/game/orders/exits`, body);

export const cancelGameOrder = (orderId: number): Promise<GameOrderReceipt> =>
  postGame(`/game/orders/${orderId}/cancel`);

// 만료 연장 — 만료 자체는 없앨 수 없다(체결 스캔 범위를 묶는 성능 장치).
export const extendGameOrder = (orderId: number): Promise<GameOrderReceipt> =>
  postGame(`/game/orders/${orderId}/extend`);

// 창업 — 적합도 미리보기는 실데이터 근거, 매출·비용은 게임 규칙이다(응답 필드 접두사로 구분).
export const fetchGameAreaFitness = (
  trdarCode: number,
  serviceCode: string,
): Promise<GameAreaFitness> =>
  getJson(`/game/areas/${trdarCode}/fitness?service_code=${encodeURIComponent(serviceCode)}`);

export const openGameStore = (body: {
  trdarCode: number;
  serviceCode: string;
  budgetKrw: number;
  staffCount: number;
  priceFactor: number;
}): Promise<GameOpenStoreReceipt> => postGame(`/game/stores`, body);

export const fetchGameStores = (): Promise<GameStoreSummary[]> => getJson(`/game/stores`);

// 운영 결정 — 다음 게임일부터 적용된다. 넣지 않은 항목은 직전 결정을 잇는다.
export const decideGameStore = (
  storeId: number,
  body: { priceFactor?: number; staffCount?: number; facilityScore?: number },
): Promise<GameStoreDecisionReceipt> => postGame(`/game/stores/${storeId}/decisions`, body);

// 폐업 — 보증금은 회수되고 인테리어는 회수되지 않는다.
export const closeGameStore = (storeId: number): Promise<GameCloseStoreReceipt> =>
  postGame(`/game/stores/${storeId}/close`);

export const fetchGameStoreDaily = (storeId: number, days = 14): Promise<GameStoreDaily> =>
  getJson(`/game/stores/${storeId}?days=${days}`);

// 분기 결산 — 조회가 곧 정산 시점이다(지연 실행). cron이 없어 밀린 분기를 여기서 확정한다.
// 멱등하므로 여러 번 불러도 안전하다.
export const fetchGameSettlements = (): Promise<GameSettlementList> =>
  getJson(`/game/settlements`);

// ── 북마크 — 관심 종목·상권. 인증은 httpOnly 쿠키가 자동 동행한다. ──
async function sendJson<T>(path: string, method: "POST" | "PUT" | "DELETE", body?: unknown): Promise<T> {
  const res = await fetch(`/api/backend${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? "요청에 실패했습니다.");
  }
  return res.json();
}

export const fetchBookmarks = (): Promise<{ items: Bookmark[] }> => getJson("/bookmarks");

export const addBookmark = (body: {
  target_type: Bookmark["target_type"];
  target_key: string;
  label: string;
}): Promise<Bookmark> => sendJson("/bookmarks", "POST", body);

export const removeBookmark = (
  targetType: Bookmark["target_type"],
  targetKey: string,
): Promise<{ deleted: boolean }> =>
  sendJson(`/bookmarks/${targetType}/${encodeURIComponent(targetKey)}`, "DELETE");

// 관심 보드(③-M7) — 북마크에 종목 신호·상권 점수를 붙여 한 번에 준다(등록 최신순 고정)
export const fetchBookmarkBoard = (): Promise<{ items: BookmarkBoardItem[] }> =>
  getJson("/bookmarks/board");

// ── 관심 대상 알림 수신 설정 — 미설정이면 백엔드가 기본 수신(true)·텔레그램 미등록 ──
export const fetchAlertSetting = (): Promise<AlertSetting> => getJson("/alert-settings");

export const saveAlertSetting = (body: {
  email_alerts: boolean;
  telegram_chat_id: string | null; // null·빈 문자열 = 텔레그램 채널 해제(I-7)
}): Promise<AlertSetting> => sendJson("/alert-settings", "PUT", body);

// ── 투자·창업 프로파일 — 자기신고 설문(밴드 기반), 사용자당 1건. ──
export const fetchProfile = (): Promise<{ profile: InvestorProfile | null }> =>
  getJson("/profile");

export const saveProfile = (
  body: Omit<InvestorProfile, "updated_at">,
): Promise<InvestorProfile> => sendJson("/profile", "PUT", body);

export const removeProfile = (): Promise<{ deleted: boolean }> =>
  sendJson("/profile", "DELETE");
