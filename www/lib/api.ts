import type {
  AreaDetail,
  AreaFitness,
  AreaRanking,
  Bookmark,
  PaperAccount,
  PaperBoard,
  PaperDecisions,
  PaperScorecard,
  AreaScoreDetail,
  AreaShowcase,
  AreaStatsDetail,
  ConversationMessage,
  ConversationSummary,
  Fundamentals,
  InvestorProfile,
  AlertSetting,
  PriceAlert,
  PriceAlertList,
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
import { tryRefreshSession } from "./authApi";

// 액세스 토큰(1시간)이 탭을 열어둔 사이 만료되면 모든 조회가 401로 죽는다(2026-09-01 실측
// 57건 — 화면 전체 "불러오지 못했습니다"). chat 경로(store.ts)와 같은 규칙으로
// 401 → 리프레시 회전 → 1회 재시도한다. 리프레시도 실패하면 원래 401을 그대로 던진다.
async function fetchWithRefresh(input: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, init);
  if (res.status === 401 && (await tryRefreshSession())) {
    return fetch(input, init);
  }
  return res;
}

// 모든 GET 조회는 next.config rewrites(/api/backend/* → FastAPI)를 경유한다.
async function getJson<T>(path: string): Promise<T> {
  const res = await fetchWithRefresh(`/api/backend${path}`);  // 세션은 httpOnly 쿠키 — 자동 동행
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

// 워치리스트 위험 신호 보드 — 종목별 analyze/forecast를 N번 부르지 않고 축적 스냅샷·일봉을 한 번에 읽는다.
// 기본 정렬은 위험 신호 순(2026-09-17 재설계 — 방향 신호는 겹침 보정 재검증 미달)
export const fetchStockBoard = (horizon = 5, limit = 40, order: "risk" | "signal" = "risk"): Promise<StockBoard> =>
  getJson(`/stock/board?horizon=${horizon}&limit=${limit}&order=${order}`);

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

export const fetchAreaFitness = (
  trdarCode: string | number,
  serviceCode: string,
): Promise<AreaFitness> =>
  getJson(`/market/trdar/${trdarCode}/fitness?service_code=${encodeURIComponent(serviceCode)}`);

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

// ── 북마크 — 관심 종목·상권. 인증은 httpOnly 쿠키가 자동 동행한다. ──
async function sendJson<T>(path: string, method: "POST" | "PUT" | "DELETE", body?: unknown): Promise<T> {
  const res = await fetchWithRefresh(`/api/backend${path}`, {
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

// 가격 도달 알림 조건([6]) — 도달 시 1회 통지 후 자동 비활성(재알림은 재등록)
// ── AI 모의투자 — 실제 매매 아님. 리더보드·곡선은 일 1회 갱신이라 폴링하지 않는다 ──
export const fetchPaperBoard = (): Promise<PaperBoard> => getJson("/stock/paper/board");
export const fetchPaperAccount = (key: string): Promise<PaperAccount> =>
  getJson(`/stock/paper/accounts/${encodeURIComponent(key)}`);
export const fetchPaperDecisions = (key: string, limit = 400): Promise<PaperDecisions> =>
  getJson(`/stock/paper/accounts/${encodeURIComponent(key)}/decisions?limit=${limit}`);
export const fetchPaperScorecard = (key: string): Promise<PaperScorecard> =>
  getJson(`/stock/paper/accounts/${encodeURIComponent(key)}/scorecard`);

export const fetchPriceAlerts = (): Promise<PriceAlertList> => getJson("/price-alerts");

export const createPriceAlert = (body: {
  ticker: string;
  target_price: number;
  direction: PriceAlert["direction"];
}): Promise<PriceAlert> => sendJson("/price-alerts", "POST", body);

export const deletePriceAlert = async (id: number): Promise<void> => {
  // 204 응답이라 sendJson(res.json 강제)을 못 쓴다 — 본문 없는 성공을 그대로 받는다
  const res = await fetchWithRefresh(`/api/backend/price-alerts/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? "요청에 실패했습니다.");
  }
};

// ── 투자·창업 프로파일 — 자기신고 설문(밴드 기반), 사용자당 1건. ──
export const fetchProfile = (): Promise<{ profile: InvestorProfile | null }> =>
  getJson("/profile");

export const saveProfile = (
  body: Omit<InvestorProfile, "updated_at">,
): Promise<InvestorProfile> => sendJson("/profile", "PUT", body);

export const removeProfile = (): Promise<{ deleted: boolean }> =>
  sendJson("/profile", "DELETE");
