"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus, MessageSquare, MapPin, CandlestickChart, Zap, ScanEye, Gamepad2, LogOut, Menu, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import Wordmark from "./Wordmark";
import EmailModal from "./EmailModal";
import { useUIStore } from "@/lib/uiStore";
import { apiLogout } from "@/lib/authApi";
import { useVisibleTabs, type TabKey } from "@/lib/useVisibleTabs";

type NavItem = {
  icon: LucideIcon;
  label: string;
  href: string;
  key?: TabKey; // 등급 게이팅 키 — 없으면 항상 노출
  children?: { label: string; href: string }[];
};

const navItems: NavItem[] = [
  { icon: Plus, label: "새로 물어보기", href: "/" },
  { icon: MessageSquare, label: "지난 대화", href: "/history", key: "history" },
  {
    icon: MapPin,
    label: "상권 분석",
    href: "/market",
    key: "market",
    children: [{ label: "상권 둘러보기", href: "/areas" }],
  },
  { icon: CandlestickChart, label: "주식 분석", href: "/stock", key: "stock" },
  // 게임은 key가 없다 = 등급 게이팅 대상이 아니다(전 유저 공개, game-harness §10-1).
  // "새로 물어보기"와 같은 취급이며 hub의 TAB_KEYS에도 넣지 않는다.
  { icon: Gamepad2, label: "게임", href: "/game" },
  {
    icon: ScanEye,
    label: "비전처리",
    href: "/vision",
    key: "vision",
    children: [{ label: "얼굴 인식", href: "/vision/faces" }],
  },
];

// 모바일 컴팩트 내비 — BottomTabBar 폐기 후 핵심 이동 경로만 아이콘으로.
// 네 번째 칸은 햄버거가 차지한다(나머지 화면·하위 항목은 전부 그 안에 있다).
const mobileNavItems: NavItem[] = [
  { icon: MapPin, label: "상권 분석", href: "/market", key: "market" },
  { icon: CandlestickChart, label: "주식 분석", href: "/stock", key: "stock" },
  { icon: Gamepad2, label: "게임", href: "/game" },
];

export default function TopNav() {
  const pathname = usePathname();
  const openAuth = useUIStore((s) => s.openAuth);
  const user = useUIStore((s) => s.user);
  const logoutStore = useUIStore((s) => s.logout);
  const logout = () => { void apiLogout(); logoutStore(); };
  // 이메일 모달과 모바일 메뉴는 동시에 열리지 않으므로 상태 하나로 둔다
  const [overlay, setOverlay] = useState<"email" | "menu" | null>(null);
  const tabs = useVisibleTabs(); // null = 로딩 중 — 게이팅 탭 미표시(사라지는 플래시 방지)

  // /rom은 자체 헤더를 가진 전체화면 챗봇 창이라 상단 내비를 비운다(어드민과 같은 이유)
  if (pathname?.startsWith("/admin") || pathname?.startsWith("/rom")) return null;

  return (
    // 모바일은 패딩·간격을 줄인다 — px-6 + gap-8이면 워드마크·아이콘 4개·로그인이
    // 375px 폭을 넘겨 헤더가 잘렸다. gap은 최소 간격일 뿐이라 넓은 화면은 ml-auto가 벌린다.
    <header className="relative h-14 flex items-center px-4 gap-1 sm:px-6 sm:gap-8">
      <Wordmark />

      <nav className="hidden sm:flex items-center gap-1">
        {navItems
          .filter((item) => !item.key || tabs?.has(item.key))
          .map(({ icon: Icon, label, href, children }) => (
          <div key={label} className="relative group">
            <Link
              href={href}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-foreground/80 hover:bg-accent hover:text-foreground transition-colors"
            >
              <Icon size={15} strokeWidth={1.75} className="text-brand" />
              {label}
            </Link>
            {children && (
              <div className="absolute left-0 top-full pt-1 hidden group-hover:block z-50">
                <div className="min-w-[140px] rounded-xl border border-border bg-surface shadow-lg py-1">
                  {children.map((child) => (
                    <Link
                      key={child.label}
                      href={child.href}
                      className="block px-4 py-2 text-sm text-foreground/80 hover:bg-accent hover:text-foreground transition-colors"
                    >
                      {child.label}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
        {tabs?.has("automation") && (
          <button
            type="button"
            onClick={() => setOverlay("email")}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-foreground/80 hover:bg-accent hover:text-foreground transition-colors"
          >
            <Zap size={15} strokeWidth={1.75} className="text-brand" />
            자동화
          </button>
        )}
      </nav>

      <EmailModal open={overlay === "email"} onClose={() => setOverlay(null)} />

      <nav className="sm:hidden ml-auto flex items-center gap-0.5" aria-label="주요 화면">
        {mobileNavItems
          .filter((item) => !item.key || tabs?.has(item.key))
          .map(({ icon: Icon, label, href }) => (
          <Link
            key={label}
            href={href}
            aria-label={label}
            className="w-8 h-8 grid place-items-center rounded-lg text-brand hover:bg-accent transition-colors"
          >
            <Icon size={18} strokeWidth={1.75} />
          </Link>
        ))}
        <button
          type="button"
          onClick={() => setOverlay((prev) => (prev === "menu" ? null : "menu"))}
          aria-label="전체 메뉴"
          aria-expanded={overlay === "menu"}
          className="w-8 h-8 grid place-items-center rounded-lg text-brand hover:bg-accent transition-colors"
        >
          <Menu size={18} strokeWidth={1.75} />
        </button>
      </nav>

      {/* 모바일 전체 메뉴 — 아이콘 3칸에 없는 화면과 하위 항목(상권 둘러보기·얼굴 인식)으로
          가는 유일한 경로다. 데스크탑은 hover 드롭다운이 그 역할을 한다. */}
      {overlay === "menu" && (
        <>
          <button
            type="button"
            aria-label="메뉴 닫기"
            onClick={() => setOverlay(null)}
            className="sm:hidden fixed inset-x-0 bottom-0 top-14 z-40 bg-black/20"
          />
          <div className="sm:hidden absolute top-full inset-x-0 z-50 border-y border-border bg-surface shadow-lg py-2">
            {navItems
              .filter((item) => !item.key || tabs?.has(item.key))
              .map(({ icon: Icon, label, href, children }) => (
              <div key={label}>
                <Link
                  href={href}
                  onClick={() => setOverlay(null)}
                  className="flex items-center gap-2.5 px-5 py-2.5 text-sm text-foreground/80 hover:bg-accent transition-colors"
                >
                  <Icon size={16} strokeWidth={1.75} className="text-brand" />
                  {label}
                </Link>
                {children?.map((child) => (
                  <Link
                    key={child.label}
                    href={child.href}
                    onClick={() => setOverlay(null)}
                    className="block pl-12 pr-5 py-2 text-sm text-foreground-muted hover:bg-accent transition-colors"
                  >
                    {child.label}
                  </Link>
                ))}
              </div>
            ))}
            {tabs?.has("automation") && (
              <button
                type="button"
                onClick={() => setOverlay("email")}
                className="w-full flex items-center gap-2.5 px-5 py-2.5 text-sm text-foreground/80 hover:bg-accent transition-colors"
              >
                <Zap size={16} strokeWidth={1.75} className="text-brand" />
                자동화
              </button>
            )}
          </div>
        </>
      )}

      <div className="sm:ml-auto flex items-center gap-2">
        {user ? (
          <>
            <span className="hidden sm:inline text-sm text-foreground/80">{user.name}님</span>
            {/* 모바일은 아이콘만 — 이름과 텍스트 버튼을 함께 두면 헤더가 넘친다(어드민 셸과 같은 처리) */}
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              aria-label="로그아웃"
              className="px-2 sm:px-3 text-foreground-muted hover:text-foreground"
            >
              <LogOut className="sm:hidden" />
              <span className="hidden sm:inline">로그아웃</span>
            </Button>
          </>
        ) : (
          <Button size="sm" onClick={() => openAuth("login")}>
            로그인
          </Button>
        )}
      </div>
    </header>
  );
}
