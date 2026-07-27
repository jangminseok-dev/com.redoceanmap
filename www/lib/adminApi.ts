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
  email: string;
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

export const fetchAdminForecasts = (
  horizon: number | null,
  limit = 50,
): Promise<AdminForecastReport> => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (horizon != null) params.set("horizon", String(horizon));
  return request(`/admin/forecasts?${params}`);
};

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
  a.click();
  URL.revokeObjectURL(url);
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
