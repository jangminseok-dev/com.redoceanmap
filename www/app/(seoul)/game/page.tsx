"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CandlestickChart, Gamepad2, Store } from "lucide-react";
import InvestPanel from "@/components/game/InvestPanel";
import StorePanel from "@/components/game/StorePanel";
import { fetchGameRulebook } from "@/lib/api";

const TABS = [
  { key: "invest", label: "모의 투자", icon: CandlestickChart },
  { key: "store", label: "상권 창업", icon: Store },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/**
 * 게임 셸 — 두 게임이 지갑 하나를 공유하므로 한 화면 안에서 탭으로 오간다.
 *
 * 워크스페이스 3패널(자료|스테이지|채팅)을 쓰지 않는다. 게임에는 채팅 패널이 붙을 자리가
 * 없고, `TAB_KEYS`에도 없어 `TabGuard`도 두지 않는다(game-harness §10).
 */
export default function GamePage() {
  const [tab, setTab] = useState<TabKey>("invest"); // 상태는 이 하나뿐이다

  // 게임 시각은 두 패널이 함께 쓰므로 셸이 한 번만 부른다(같은 쿼리 키라 캐시 공유)
  const rulebookQ = useQuery({
    queryKey: ["game-rulebook"],
    queryFn: fetchGameRulebook,
    staleTime: 10 * 60_000,
  });
  const clock = rulebookQ.data;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 sm:px-6 py-6 sm:py-8">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="grid place-items-center w-9 h-9 rounded-xl bg-brand/10 text-brand">
          <Gamepad2 size={19} strokeWidth={1.9} />
        </span>
        <h1 className="text-xl font-bold tracking-tight">게임</h1>

        {clock && (
          <span className="text-sm text-foreground-muted">
            {clock.gameQuarter}분기 {clock.dayOfQuarter}일차
            <span className="mx-1.5 text-border">·</span>
            시즌 {Math.ceil(clock.ticksRemaining / 60 / 24)}일 남음
          </span>
        )}
      </header>

      <p className="mt-3 text-sm text-foreground-muted leading-relaxed">
        실제 1시간이 게임 1일입니다. 두 게임은 지갑 하나를 함께 씁니다 — 투자로 번 돈으로
        창업하고, 가게 수익이 다시 투자금이 됩니다.
      </p>

      <nav className="mt-5 inline-flex rounded-xl border border-border p-1 bg-surface">
        {TABS.map(({ key, label, icon: Icon }) => {
          const active = tab === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              aria-current={active}
              className={`inline-flex items-center gap-1.5 px-4 h-9 rounded-lg text-sm font-medium transition-colors ${
                active ? "bg-brand text-white" : "text-foreground-muted hover:text-foreground"
              }`}
            >
              <Icon size={15} strokeWidth={1.9} />
              {label}
            </button>
          );
        })}
      </nav>

      {/* 패널은 한 번만 마운트하고 표시만 전환한다 — 지도·차트 이중 인스턴스 방지
          (WorkspaceShell과 같은 이유) */}
      <div className="mt-5">
        <div className={tab === "invest" ? "" : "hidden"}>
          <InvestPanel />
        </div>
        <div className={tab === "store" ? "" : "hidden"}>
          <StorePanel />
        </div>
      </div>
    </div>
  );
}
