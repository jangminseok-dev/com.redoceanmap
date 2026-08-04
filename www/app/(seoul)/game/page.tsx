"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CandlestickChart, Store } from "lucide-react";
import InvestPanel from "@/components/game/InvestPanel";
import StorePanel from "@/components/game/StorePanel";
import { fetchGameRulebook } from "@/lib/api";

// 모의 투자와 지수 선물을 하나로 합쳤다 — 지갑이 하나이고 지수가 그 종목들로 만들어지므로,
// 페이지를 가르는 대신 투자 탭 안에서 [주식 | 지수 선물] 세그먼트로 오간다.
const TABS = [
  { key: "invest", label: "투자", icon: CandlestickChart },
  { key: "store", label: "상권 창업", icon: Store },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/**
 * 게임 셸 — 투자 탭은 **화면 높이를 꽉 채우고 내부에서만 스크롤한다**(레퍼런스 토스증권).
 *
 * 예전에는 페이지가 세로로 흐르고 안내·자산·알림 카드가 위쪽 절반을 먹어서
 * 정작 종목 표는 스크롤해야 나왔다. 표가 주인공인 화면에서 표가 접혀 있으면 안 된다.
 * 상권 창업은 읽기 중심이라 예전처럼 세로로 흐른다.
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
    <div className="h-full flex flex-col min-h-0">
      <header className="shrink-0 flex flex-wrap items-center gap-x-3 gap-y-2 px-4 sm:px-6 pt-3 pb-2">
        <nav className="flex items-center gap-1.5" aria-label="게임">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              aria-current={tab === key}
              className={`inline-flex items-center gap-1.5 h-9 px-3.5 rounded-full text-sm font-medium transition-colors duration-150 ${
                tab === key
                  ? "bg-brand text-white"
                  : "border border-border text-foreground-muted hover:bg-accent hover:text-foreground"
              }`}
            >
              <Icon size={15} strokeWidth={1.9} />
              {label}
            </button>
          ))}
        </nav>

        {clock && (
          <p className="text-xs text-foreground-muted">
            {clock.gameQuarter}분기 {clock.gameDay}일차 · 실제 1시간이 게임 1일 · 가상 주가입니다
          </p>
        )}
      </header>

      {/* 패널은 한 번만 마운트하고 표시만 전환한다 — 차트 이중 인스턴스 방지 */}
      <div className={`flex-1 min-h-0 ${tab === "invest" ? "flex flex-col" : "hidden"}`}>
        <InvestPanel />
      </div>
      <div className={`flex-1 min-h-0 overflow-y-auto ${tab === "store" ? "" : "hidden"}`}>
        <div className="mx-auto w-full max-w-6xl px-4 sm:px-6 pb-8">
          <StorePanel />
        </div>
      </div>
    </div>
  );
}
