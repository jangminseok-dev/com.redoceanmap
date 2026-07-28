import type {
  AreaDetail,
  AreaRanking,
  AreaScoreDetail,
  AreaShowcase,
  AreaStatsDetail,
  ConversationMessage,
  ConversationSummary,
  Fundamentals,
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
