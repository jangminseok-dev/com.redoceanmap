"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  CandlestickChart,
  Compass,
  Gamepad2,
  LogOut,
  MapPin,
  MessageSquare,
  MoreHorizontal,
  Plus,
  ScanEye,
  ScanFace,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import Wordmark from "@/components/seoul/Wordmark";
import EmailModal from "@/components/seoul/EmailModal";
import { useUIStore } from "@/lib/uiStore";
import { apiLogout } from "@/lib/authApi";
import { useVisibleTabs, type TabKey } from "@/lib/useVisibleTabs";

type NavItem = {
  icon: LucideIcon;
  label: string;
  href: string;
  key?: TabKey; // 등급 게이팅 키 — 없으면 항상 노출
};

// 레일·하단탭에 상주하는 주 항목. 라벨은 2~3글자로 고정한다 —
// 72px 폭에서 12px 라벨(스케일 하한)이 줄바꿈 없이 들어가는 길이다.
const PRIMARY: NavItem[] = [
  { icon: Plus, label: "질문", href: "/" },
  { icon: MapPin, label: "상권", href: "/market", key: "market" },
  { icon: CandlestickChart, label: "주식", href: "/stock", key: "stock" },
  // 게임은 등급 게이팅 대상이 아니다(전 유저 공개) — key가 없는 것이 의도다
  { icon: Gamepad2, label: "게임", href: "/game" },
];

// 더보기 시트에만 있는 부 항목. 매일 쓰지 않는 것과 하위 화면을 여기로 내린다.
const SECONDARY: NavItem[] = [
  { icon: MessageSquare, label: "지난 대화", href: "/history", key: "history" },
  { icon: Compass, label: "상권 둘러보기", href: "/areas", key: "market" },
  { icon: ScanEye, label: "비전처리", href: "/vision", key: "vision" },
  { icon: ScanFace, label: "얼굴 인식", href: "/vision/faces", key: "vision" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const openAuth = useUIStore((s) => s.openAuth);
  const user = useUIStore((s) => s.user);
  const logoutStore = useUIStore((s) => s.logout);
  const tabs = useVisibleTabs(); // null = 로딩 중 — 게이팅 항목 미표시(사라지는 플래시 방지)
  // 더보기 시트와 자동화 모달은 동시에 열리지 않으므로 상태 하나로 둔다
  const [overlay, setOverlay] = useState<"more" | "email" | null>(null);

  const logout = () => {
    void apiLogout();
    logoutStore();
    setOverlay(null);
  };
  const visible = (item: NavItem) => !item.key || tabs?.has(item.key);
  // "/"는 완전 일치로만 활성 — 아니면 모든 경로에서 켜진다
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : !!pathname?.startsWith(href);

  // 어드민(AdminShell)과 /rom(전체화면 챗봇)은 자체 셸을 가진다 — 레일을 씌우지 않는다.
  // hook 호출 뒤에 분기한다(조건부 hook 금지).
  if (pathname?.startsWith("/admin") || pathname?.startsWith("/rom")) return <>{children}</>;

  const primary = PRIMARY.filter(visible);
  const secondary = SECONDARY.filter(visible);

  return (
    <div className="h-dvh flex bg-background text-foreground">
      {/* 데스크탑 레일 — 상단 헤더를 대신한다. 세로 56px을 화면에 돌려준다. */}
      <nav
        className="hidden lg:flex flex-col items-center w-[72px] shrink-0 border-r border-border bg-surface"
        aria-label="주요 화면"
      >
        <div className="h-14 grid place-items-center">
          <Wordmark iconOnly />
        </div>

        <div className="flex flex-col gap-1 w-full px-2">
          {primary.map(({ icon: Icon, label, href }) => (
            <RailItem key={href} icon={Icon} label={label} href={href} active={isActive(href)} />
          ))}
          <RailButton
            icon={MoreHorizontal}
            label="더보기"
            onClick={() => setOverlay("more")}
            expanded={overlay === "more"}
          />
        </div>

        <div className="mt-auto w-full px-2 pb-3">
          {user ? (
            <button
              type="button"
              onClick={logout}
              title={`${user.name}님 — 로그아웃`}
              className="w-full flex flex-col items-center gap-1 py-2.5 rounded-xl text-foreground-muted hover:bg-accent hover:text-foreground transition-colors"
            >
              <LogOut size={20} strokeWidth={1.75} />
              <span className="text-xs">로그아웃</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => openAuth("login")}
              className="w-full flex flex-col items-center gap-1 py-2.5 rounded-xl text-brand hover:bg-accent transition-colors"
            >
              <span className="grid place-items-center w-8 h-8 rounded-full bg-brand text-white text-sm font-semibold">
                {"→"}
              </span>
              <span className="text-xs font-medium">로그인</span>
            </button>
          )}
        </div>
      </nav>

      {/* 본문 — 모바일에서는 하단 탭바 높이만큼 아래를 비운다 */}
      <div className="flex-1 min-w-0 flex flex-col min-h-0 pb-[calc(4rem+env(safe-area-inset-bottom))] lg:pb-0">
        {children}
      </div>

      {/* 모바일 하단 탭 — 엄지가 닿는 자리. AdminShell과 같은 safe-area 처리. */}
      <nav
        className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t border-border bg-surface/95 backdrop-blur-md"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        aria-label="주요 화면"
      >
        <div className="flex items-stretch h-16">
          {primary.map(({ icon: Icon, label, href }) => (
            <TabItem key={href} icon={Icon} label={label} href={href} active={isActive(href)} />
          ))}
          <button
            type="button"
            onClick={() => setOverlay("more")}
            aria-expanded={overlay === "more"}
            className="flex-1 flex flex-col items-center justify-center gap-1 text-foreground-muted transition-colors"
          >
            <MoreHorizontal size={21} strokeWidth={1.75} />
            <span className="text-xs">더보기</span>
          </button>
        </div>
      </nav>

      <Dialog open={overlay === "more"} onOpenChange={(open) => !open && setOverlay(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>전체 메뉴</DialogTitle>
          </DialogHeader>

          {!user && (
            <Button size="lg" className="w-full" onClick={() => { setOverlay(null); openAuth("login"); }}>
              로그인
            </Button>
          )}

          <div className="flex flex-col">
            {secondary.map(({ icon: Icon, label, href }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOverlay(null)}
                className="flex items-center gap-3 px-2 py-3 rounded-xl text-sm hover:bg-accent transition-colors"
              >
                <Icon size={17} strokeWidth={1.75} className="text-brand" />
                {label}
              </Link>
            ))}
            {tabs?.has("automation") && (
              <button
                type="button"
                onClick={() => setOverlay("email")}
                className="flex items-center gap-3 px-2 py-3 rounded-xl text-sm hover:bg-accent transition-colors"
              >
                <Zap size={17} strokeWidth={1.75} className="text-brand" />
                자동화
              </button>
            )}
            {user && (
              <button
                type="button"
                onClick={logout}
                className="lg:hidden flex items-center gap-3 px-2 py-3 rounded-xl text-sm text-foreground-muted hover:bg-accent transition-colors"
              >
                <LogOut size={17} strokeWidth={1.75} />
                로그아웃 ({user.name}님)
              </button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <EmailModal open={overlay === "email"} onClose={() => setOverlay(null)} />
    </div>
  );
}

// 레일 항목 — 활성 상태를 브랜드 적색 **면**으로 칠한다. 크림 배경 위에서 적색이
// 실제로 등장하는 첫 자리다(그전까지 적색은 아이콘 틴트와 버튼에만 있었다).
function RailItem({
  icon: Icon,
  label,
  href,
  active,
}: {
  icon: LucideIcon;
  label: string;
  href: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`flex flex-col items-center gap-1 py-2.5 rounded-xl transition-colors ${
        active ? "bg-brand text-white" : "text-foreground-muted hover:bg-accent hover:text-foreground"
      }`}
    >
      <Icon size={20} strokeWidth={active ? 2.1 : 1.75} />
      <span className="text-xs font-medium">{label}</span>
    </Link>
  );
}

function RailButton({
  icon: Icon,
  label,
  onClick,
  expanded,
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  expanded: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={expanded}
      className="flex flex-col items-center gap-1 py-2.5 rounded-xl text-foreground-muted hover:bg-accent hover:text-foreground transition-colors"
    >
      <Icon size={20} strokeWidth={1.75} />
      <span className="text-xs font-medium">{label}</span>
    </button>
  );
}

// 모바일 탭 — 레일과 달리 면을 칠하지 않는다. 하단 바에서 칠하면 너무 무겁고,
// 색+굵기만으로 충분히 구분된다(AdminShell과 같은 처리).
function TabItem({
  icon: Icon,
  label,
  href,
  active,
}: {
  icon: LucideIcon;
  label: string;
  href: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`flex-1 flex flex-col items-center justify-center gap-1 transition-colors ${
        active ? "text-brand" : "text-foreground-muted"
      }`}
    >
      <Icon size={21} strokeWidth={active ? 2.2 : 1.75} />
      <span className="text-xs font-medium">{label}</span>
    </Link>
  );
}
