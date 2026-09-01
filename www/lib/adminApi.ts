import { ApiError } from "./api";

/* ── 타입 (백엔드 admin 스키마 1:1) ── */

export type AdminMe = { user_id: number; permissions: string[] };

export type AdminMonthCount = { month: string; count: number };
export type AdminCategoryCount = { category: string; count: number };
export type AdminRecentRecommendation = {
  id: number;
  trdar_code: number;
  trdar_name: string;
  district_name: string;
  category: string;
  created_at: string;
};

// 분석 질문 수요 — 워치리스트 자동 편입(auto:demand)의 판단 재료
export type AdminStockDemand = {
  ticker: string;
  ask_count: number;
  last_asked_at: string;
};

export type AdminDashboard = {
  member_total: number;
  member_new_this_month: number;
  area_count: number;
  latest_quarter: string | null;
  recommendation_total: number;
  recommendation_today: number;
  monthly: AdminMonthCount[];
  top_categories: AdminCategoryCount[];
  recent: AdminRecentRecommendation[];
  stock_demands: AdminStockDemand[];
};

export type AdminAreaRow = {
  trdar_code: number;
  trdar_name: string;
  gu_name: string;
  dong_name: string;
  store_count: number | null;
  closure_rate: number | null;
  monthly_sales: number | null;
};

export type AdminMember = {
  id: number;
  email: string | null; // 카카오 모바일 가입 회원은 이메일이 없다(선택 동의)
  name: string;
  joined_at: string | null;
  marketing_agreed: boolean;
  roles: string[];
  suspended_at: string | null;
  deleted_at: string | null;
};

export type AdminMembersPage = { total: number; items: AdminMember[] };

export type AdminRole = { code: string; name: string; permissions: string[] };

export type AdminGrade = { code: string; name: string; tabs: string[]; member_count: number };

export type AdminRecommendationLog = {
  id: number;
  trdar_code: number;
  trdar_name: string;
  district_name: string;
  category: string;
  reason: string;
  created_at: string;
};

export type AdminRecommendationLogs = {
  total: number;
  today: number;
  items: AdminRecommendationLog[];
};

export type AdminDatasetStat = {
  key: string;
  name: string;
  row_count: number;
  latest_label: string | null;
  latest_at: string | null;
  freshness: "fresh" | "late" | "stale" | "unknown" | "unscheduled";
  expected: string | null;
  age_seconds: number | null;
};

export type AdminAuditEntry = {
  id: number;
  actor_id: number;
  action: string;
  detail: string;
  created_at: string;
};

export type AdminForecastKpi = {
  total: number;
  scored: number;
  pending: number;
  hit_rate: number | null;
  up_hit_rate: number | null;
  down_hit_rate: number | null;
};

export type AdminForecastGroupStat = {
  scored: number;
  hit_rate: number | null;
  avg_realized_return_pct: number | null;
};

export type AdminForecastSignalStat = {
  key: string;
  n: number;
  hits: number;
  hit_rate: number | null;
};

export type AdminForecastRegimeStat = {
  regime: string; // BULL | BEAR | HIGH_VOL | NONE
  scored: number;
  hit_rate: number | null;
  avg_realized_return_pct: number | null;
};

export type AdminForecastSnapshot = {
  ticker: string;
  as_of: string;
  horizon_days: number;
  direction: string;
  base_price: number;
  score: number;
  // ⚠ 이름과 달리 '그 방향의 과거 적중률'이다 — 적중 재정의(3d8ecbb) 이후
  // UP 행은 변동성 초과 상승, DOWN 행은 초과 하락 적중률(화면 라벨: 방향 적중률).
  up_rate: number | null;
  ready: boolean;
  evaluated_at: string | null;
  realized_return_pct: number | null;
  hit: boolean | null;
  regime: string | null;
  earnings_veto: boolean;
};

export type AdminForecastReport = {
  kpi: AdminForecastKpi;
  by_horizon: (AdminForecastGroupStat & { horizon_days: number })[];
  by_direction: (AdminForecastGroupStat & { direction: string })[];
  by_regime: AdminForecastRegimeStat[];
  by_signal: AdminForecastSignalStat[];
  recent: AdminForecastSnapshot[];
};

export type AdminGradeOutcomeRow = {
  grade: string;
  n: number;
  avg_rel_floating_qoq: number | null;
  median_rel_floating_qoq: number | null;
  positive_share: number | null;
  avg_sales_qoq: number | null;
  sales_n: number;
};

export type AdminComponentRow = {
  key: string;
  n: number;
  spearman: number | null;
  top_minus_bottom_quintile: number | null;
};

export type AdminMarketBacktestReport = {
  ran_at: string;
  params: Record<string, string | null>;
  n_observations: number;
  n_areas: number;
  base_quarters: number[];
  grade_outcomes: AdminGradeOutcomeRow[];
  component_predictiveness: AdminComponentRow[];
};

/* ── 요청 헬퍼 — lib/api.ts의 getJson 패턴 + 쓰기 메서드 ── */


// ── 게임 운영 (/admin/game) ──
// 주가 개입은 **지금부터 앞으로만** 적용된다 — 과거 주가는 바뀌지 않는다.
export type AdminGameWallet = {
  user_id: number;
  email: string;
  exists: boolean;
  cash_krw: number;
  epoch_id: number;
  rule_version: string;
  open_position_count: number;
  ledger_total_krw: number;
  ledger_matches: boolean;
};

export type AdminGameGrant = {
  user_id: number;
  amount_krw: number;
  cash_krw: number;
  game_day: number;
};

export type AdminGameSymbol = {
  symbol: string;
  name: string;
  sector_group: string;
  price_krw: number;
  meme: boolean;
};

export type AdminGameIntervention = {
  id: number;
  scope: "symbol" | "sector" | "market";
  target: string;
  target_name: string;
  from_game_day: number;
  shock_pct: number;
  drift_pct_per_day: number;
  duration_days: number;
  headline: string;
  note: string | null;
  in_effect: boolean;
};

export type AdminGameReportedContent = {
  target_type: "post" | "comment";
  target_id: number;
  symbol: string;
  author: string; // 게임이 만든 고정 가명 — 실명·이메일 아님
  body: string;
  report_count: number;
  reasons: string[];
  reported_at: string;
  hidden: boolean; // 이미 내려간 글 — 되돌릴 수 있게 목록에 남는다
};

export type AdminGameBoard = {
  symbols: AdminGameSymbol[];
  sector_groups: string[];
  interventions: AdminGameIntervention[];
  max_shock_pct: number;
  max_drift_pct_per_day: number;
  max_duration_days: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/backend${path}`, {
    ...init,
    headers: { ...(init?.body ? { "Content-Type": "application/json" } : {}) },  // 세션은 httpOnly 쿠키
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? "요청에 실패했습니다.");
  }
  return res.json();
}

/* ── fetcher ── */

export const fetchAdminMe = (): Promise<AdminMe> => request("/admin/me");

export const fetchAdminDashboard = (): Promise<AdminDashboard> => request("/admin/dashboard");

export const fetchAdminAreas = (): Promise<{ areas: AdminAreaRow[] }> => request("/admin/areas");

export const fetchAdminMembers = (
  search: string,
  limit: number,
  offset: number,
): Promise<AdminMembersPage> => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (search) params.set("search", search);
  return request(`/admin/members?${params}`);
};

export const fetchAdminRoles = (): Promise<{ roles: AdminRole[] }> =>
  request("/admin/members/roles");

export const grantAdminRole = (userId: number, roleCode: string): Promise<AdminMember> =>
  request(`/admin/members/${userId}/roles`, {
    method: "POST",
    body: JSON.stringify({ role_code: roleCode }),
  });

export const revokeAdminRole = (userId: number, roleCode: string): Promise<AdminMember> =>
  request(`/admin/members/${userId}/roles/${encodeURIComponent(roleCode)}`, {
    method: "DELETE",
  });

export const suspendMember = (userId: number, reason: string): Promise<AdminMember> =>
  request(`/admin/members/${userId}/suspend`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });

export const reinstateMember = (userId: number): Promise<AdminMember> =>
  request(`/admin/members/${userId}/reinstate`, { method: "POST", body: JSON.stringify({}) });

export const revokeMemberSessions = (userId: number): Promise<{ revoked: number }> =>
  request(`/admin/members/${userId}/revoke-sessions`, { method: "POST", body: JSON.stringify({}) });

export const withdrawMember = (userId: number): Promise<AdminMember> =>
  request(`/admin/members/${userId}/withdraw`, { method: "POST", body: JSON.stringify({}) });

export const fetchAdminGrades = (): Promise<{ grades: AdminGrade[] }> =>
  request("/admin/grades");

export const createAdminGrade = (code: string, name: string, tabs: string[]): Promise<AdminGrade> =>
  request("/admin/grades", { method: "POST", body: JSON.stringify({ code, name, tabs }) });

export const updateAdminGrade = (
  code: string,
  body: { name?: string; tabs?: string[] },
): Promise<AdminGrade> =>
  request(`/admin/grades/${encodeURIComponent(code)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteAdminGrade = (code: string): Promise<{ deleted: string }> =>
  request(`/admin/grades/${encodeURIComponent(code)}`, { method: "DELETE" });

export const fetchAdminRecommendations = (limit = 50): Promise<AdminRecommendationLogs> =>
  request(`/admin/recommendations?limit=${limit}`);

export const fetchAdminDataSources = (): Promise<{ datasets: AdminDatasetStat[] }> =>
  request("/admin/data-sources");

export const fetchAdminAudit = (limit = 50): Promise<{ items: AdminAuditEntry[] }> =>
  request(`/admin/audit?limit=${limit}`);

export type AdminQuestionRow = {
  conversation_id: number;
  question: string;
  answer_kind: string;
  asked_at: string;
};

export type AdminQuestionBoard = {
  window_days: number;
  total_questions: number;
  kinds: { kind: string; count: number; share_pct: number }[];
  nonseoul_regions: { region: string; count: number }[];
  recent: AdminQuestionRow[];
};

export const fetchAdminQuestions = (days = 30, limit = 50): Promise<AdminQuestionBoard> =>
  request(`/admin/questions?days=${days}&limit=${limit}`);

export const fetchAdminForecasts = (
  horizon: number | null,
  limit = 50,
): Promise<AdminForecastReport> => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (horizon != null) params.set("horizon", String(horizon));
  return request(`/admin/forecasts?${params}`);
};

export type AdminEventBucket = {
  key: string;
  n: number;
  avg_return_pct: number;
  excess_pct: number; // 기준선 대비 — 절대값이 아니라 이 값으로 읽는다
  positive_rate: number;
  reliable: boolean;
};

// 분 단위 지평(E1) — 5분봉으로 잰 발행 직후 반응. 구버전 리포트에는 없다.
export type AdminShortHorizon = {
  horizon_minutes: number;
  total: number;
  baseline_pct: number;
  top_week_share: number;
  warnings: string[];
  coverage_note: string; // 5분봉 보유 구간 — 표본 수를 일간과 직접 비교하면 안 되는 이유
  by_event: AdminEventBucket[];
  by_sentiment: AdminEventBucket[];
};

export type AdminNewsEventStudyReport = {
  ran_at: string;
  params: Record<string, unknown>;
  horizon_days: number;
  total: number;
  baseline_pct: number;
  top_week_share: number;
  warnings: string[];
  by_event: AdminEventBucket[];
  by_sentiment: AdminEventBucket[];
  short_horizon?: AdminShortHorizon[]; // 구버전 응답에는 필드 자체가 없다
};

export const fetchAdminNewsEventStudy = (): Promise<{
  report: AdminNewsEventStudyReport | null;
}> => request("/admin/news-event-study");

// ── GET /admin/forecast-refit (가중치 재적합 — 리더보드 + 조합 이력) ──

export type AdminRefitCandidate = {
  up_threshold: number;
  w_rsi: number;
  w_trend: number;
  w_bb: number;
  w_obv: number;
  w_momentum: number;
  n: number;
  hits: number;
  hit_rate: number | null;
  baseline: number; // 이 후보가 신호를 낸 종목들의 기준선(신호 수 가중)
  wilson_lower: number;
  is_current: boolean;
  gate_passed: boolean; // n≥100 + Wilson 하한 > baseline
};

export type AdminRefitBoard = {
  horizon_days: number;
  total: number;
  baseline_up_rate: number;
  current: AdminRefitCandidate | null;
  rows: AdminRefitCandidate[];
};

export type AdminRefitReport = {
  ran_at: string;
  params: Record<string, unknown>;
  gate_horizon: number;
  promote: boolean;
  winner: AdminRefitCandidate | null;
  reasons: string[];
  boards: AdminRefitBoard[];
};

export type AdminSignalConfig = {
  key: string;
  is_active: boolean;
  source: string; // seed | refit
  up_threshold: number;
  down_threshold: number;
  w_sentiment: number;
  w_rsi: number;
  w_trend: number;
  w_bb: number;
  w_obv: number;
  w_momentum: number;
  created_at: string;
  activated_at: string | null;
};

export const fetchAdminForecastRefit = (): Promise<{
  report: AdminRefitReport | null;
  history: AdminSignalConfig[];
}> => request("/admin/forecast-refit");

export const fetchAdminMarketBacktest = (): Promise<{
  report: AdminMarketBacktestReport | null;
}> => request("/admin/market-backtest");

// CSV 내보내기용 — 서버 limit 상한(100)에 맞춰 offset 순회로 전량 수집
export const fetchAllAdminMembers = async (search: string): Promise<AdminMember[]> => {
  const all: AdminMember[] = [];
  let offset = 0;
  for (;;) {
    const page = await fetchAdminMembers(search, 100, offset);
    all.push(...page.items);
    offset += 100;
    if (all.length >= page.total || page.items.length === 0) return all;
  }
};


export const fetchAdminGameWallet = (userId: number): Promise<AdminGameWallet> =>
  request(`/admin/game/wallets/${userId}`);

export const grantAdminGameCapital = (
  userId: number,
  body: { amount_krw: number; reason: string },
): Promise<AdminGameGrant> =>
  request(`/admin/game/wallets/${userId}/grants`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const fetchAdminGameBoard = (): Promise<AdminGameBoard> => request("/admin/game/market");

export const interveneAdminGamePrice = (body: {
  scope: string;
  target: string;
  shock_pct: number;
  drift_pct_per_day: number;
  duration_days: number;
  headline: string;
  note: string | null;
  target_price_krw: number | null;
}): Promise<AdminGameIntervention> =>
  request("/admin/game/interventions", { method: "POST", body: JSON.stringify(body) });

export const fetchAdminGameReports = (
  limit = 50,
): Promise<AdminGameReportedContent[]> =>
  request(`/admin/game/community/reports?limit=${limit}`);

async function requestVoid(path: string, body: unknown): Promise<void> {
  // 204 응답 엔드포인트용 — request()는 res.json()을 강제해서 못 쓴다
  const res = await fetch(`/api/backend${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? "요청에 실패했습니다.");
  }
}

export const hideAdminGameContent = (body: {
  target_type: string;
  target_id: number;
  reason: string;
}): Promise<void> => requestVoid("/admin/game/community/hide", body);

export const unhideAdminGameContent = (body: {
  target_type: string;
  target_id: number;
}): Promise<void> => requestVoid("/admin/game/community/unhide", body);

// BOM 포함 CSV 다운로드 (엑셀 한글 호환)
export const downloadCsv = (filename: string, header: string[], rows: (string | number)[][]) => {
  const escape = (v: string | number) => {
    let s = String(v);
    // CSV 수식 주입 방어 — 사용자 제어 값(이름·이메일)이 =,+,-,@로 시작하면
    // 스프레드시트가 수식으로 실행하므로 작은따옴표로 무력화한다.
    if (/^[=+\-@]/.test(s)) s = `'${s}`;
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [header, ...rows].map((r) => r.map(escape).join(",")).join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
};

/* ── 표시 헬퍼 ── */

// "20251" → "2025년 1분기", ISO 문자열 → "YYYY-MM-DD"
export const formatLatestLabel = (label: string | null): string => {
  if (!label) return "—";
  if (/^\d{5}$/.test(label)) return `${label.slice(0, 4)}년 ${label.slice(4)}분기`;
  return label.slice(0, 10);
};

// 경과 시간 → "12분 전". 서버가 준 age_seconds만 쓴다(클라이언트 시계·하이드레이션 불일치 회피).
export const formatAge = (seconds: number | null): string => {
  if (seconds == null) return "—";
  if (seconds < 60) return "방금 전";
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
};

export const formatDate = (iso: string | null): string => (iso ? iso.slice(0, 10) : "—");

// 원 단위 월매출 → "8,420만" 표기
export const formatSalesMan = (won: number | null): string =>
  won == null ? "—" : `${Math.round(won / 10_000).toLocaleString()}만`;
