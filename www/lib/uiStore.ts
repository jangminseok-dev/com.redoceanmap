import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AuthMode = "login" | "signup";

export type User = {
  id: number;
  name: string;
  email: string;
};

type UIState = {
  authOpen: boolean;
  authMode: AuthMode;
  user: User | null;
  token: string | null;
  openAuth: (mode: AuthMode) => void;
  closeAuth: () => void;
  setAuthMode: (mode: AuthMode) => void;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  logout: () => void;
};

export const useUIStore = create<UIState>((set) => ({
  authOpen: false,
  authMode: "login",
  user: null,
  token: null,
  openAuth: (mode) => set({ authOpen: true, authMode: mode }),
  closeAuth: () => set({ authOpen: false }),
  setAuthMode: (mode) => set({ authMode: mode }),
  setUser: (user) => set({ user }),
  setToken: (token) => set({ token }),
  logout: () => set({ user: null, token: null }),
}));

// 테마 — 라이트가 기본, 다크는 토글로 켜는 보조 테마. 초기값은 layout.tsx의 인라인
// 스크립트가 첫 페인트 전에 <html data-theme>으로 심는다(시스템 선호 → 수동 오버라이드 순).
// 이 스토어는 그 결과를 읽어 시작하고, 토글 시 DOM 속성과 저장값을 함께 갱신한다.
export const THEME_KEY = "rom-theme";
export type Theme = "light" | "dark";

type ThemeState = {
  theme: Theme;
  toggleTheme: () => void;
};

export const useThemeStore = create<ThemeState>((set) => ({
  theme:
    typeof document !== "undefined" && document.documentElement.dataset.theme === "dark"
      ? "dark"
      : "light",
  toggleTheme: () =>
    set((s) => {
      const next: Theme = s.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        // 저장 실패(프라이빗 모드 등)해도 세션 내 전환은 동작한다
      }
      return { theme: next };
    }),
}));

// 최근 본 종목/상권 — 레일 "최근" 스택(최대 3, 핸드오프 §공통 셸).
// 레일이 "지금 보는 것과 최근 것"을 기억해야 워크스페이스를 떠났다 돌아오는 왕복이 짧아진다.
export type RecentItem = { type: "stock" | "market"; id: string; label: string };

type RecentState = {
  items: RecentItem[];
  push: (item: RecentItem) => void;
};

export const useRecentStore = create<RecentState>()(
  persist(
    (set) => ({
      items: [],
      push: (item) =>
        set((s) => ({
          items: [
            item,
            ...s.items.filter((i) => !(i.type === item.type && i.id === item.id)),
          ].slice(0, 3),
        })),
    }),
    { name: "rom-recent-items" },
  ),
);

// 표시 밀도 — 기본은 초보(결론 위주). 전문가는 원 수치·표본·전체 지표까지 펼친다.
// 매 방문마다 다시 켜게 하면 전문가에게 성가시므로 이 값만 로컬에 남긴다(민감정보 아님).
type DensityState = {
  expert: boolean;
  toggleExpert: () => void;
};

export const useDensityStore = create<DensityState>()(
  persist(
    (set) => ({
      expert: false,
      toggleExpert: () => set((s) => ({ expert: !s.expert })),
    }),
    { name: "rom-display-density" },
  ),
);
