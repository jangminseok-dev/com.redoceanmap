"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Plus, MessageSquare, MapPin, CandlestickChart, Zap, ScanEye, type LucideIcon } from "lucide-react";
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
  {
    icon: ScanEye,
    label: "비전처리",
    href: "/vision",
    key: "vision",
    children: [{ label: "얼굴 인식", href: "/vision/faces" }],
  },
];

// 모바일 컴팩트 내비 — BottomTabBar 폐기 후 핵심 이동 경로만 아이콘으로
const mobileNavItems: NavItem[] = [
  { icon: MapPin, label: "상권 분석", href: "/market", key: "market" },
  { icon: CandlestickChart, label: "주식 분석", href: "/stock", key: "stock" },
  { icon: MessageSquare, label: "지난 대화", href: "/history", key: "history" },
];

export default function TopNav() {
  const pathname = usePathname();
  const openAuth = useUIStore((s) => s.openAuth);
  const user = useUIStore((s) => s.user);
  const logoutStore = useUIStore((s) => s.logout);
  const logout = () => { void apiLogout(); logoutStore(); };
  const [emailOpen, setEmailOpen] = useState(false);
  const tabs = useVisibleTabs(); // null = 로딩 중 — 게이팅 탭 미표시(사라지는 플래시 방지)

  if (pathname?.startsWith("/admin")) return null;

  return (
    <header className="h-14 flex items-center px-6 gap-8">
      <Wordmark />

      <nav className="hidden sm:flex items-center gap-1">
        {navItems
          .filter((item) => !item.key || tabs?.has(item.key))
          .map(({ icon: Icon, label, href, children }) => (
          <div key={label} className="relative group">
            <Link
              href={href}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-foreground/80 hover:bg-black/5 hover:text-foreground transition-colors"
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
                      className="block px-4 py-2 text-sm text-foreground/80 hover:bg-black/5 hover:text-foreground transition-colors"
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
            onClick={() => setEmailOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-foreground/80 hover:bg-black/5 hover:text-foreground transition-colors"
          >
            <Zap size={15} strokeWidth={1.75} className="text-brand" />
            자동화
          </button>
        )}
      </nav>

      <EmailModal open={emailOpen} onClose={() => setEmailOpen(false)} />

      <nav className="sm:hidden ml-auto flex items-center gap-0.5" aria-label="주요 화면">
        {mobileNavItems
          .filter((item) => !item.key || tabs?.has(item.key))
          .map(({ icon: Icon, label, href }) => (
          <Link
            key={label}
            href={href}
            aria-label={label}
            className="w-9 h-9 grid place-items-center rounded-lg text-brand hover:bg-black/5 transition-colors"
          >
            <Icon size={18} strokeWidth={1.75} />
          </Link>
        ))}
      </nav>

      <div className="sm:ml-auto flex items-center gap-2">
        {user ? (
          <>
            <span className="text-sm text-foreground/80">{user.name}님</span>
            <button
              type="button"
              onClick={logout}
              className="text-sm font-medium text-foreground-muted hover:text-foreground px-3 py-1.5 rounded-full hover:bg-black/5 transition-colors"
            >
              로그아웃
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => openAuth("login")}
            className="text-sm font-medium bg-brand text-white px-4 py-1.5 rounded-full hover:bg-brand-deep transition-colors"
          >
            로그인
          </button>
        )}
      </div>
    </header>
  );
}
