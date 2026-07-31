"use client";

import { TrendingDown, TrendingUp } from "lucide-react";
import type { GameMarketEvent } from "@/lib/types";

const SCOPE_LABEL: Record<GameMarketEvent["scope"], string> = {
  symbol: "종목",
  sector: "업종",
  market: "시장",
};

/**
 * 시장 뉴스 — 최근 호재·악재.
 *
 * 저장된 로그가 아니라 **매번 재현되는 값**이다. 같은 틱이면 누가 언제 봐도 같은 목록이라
 * 모든 참가자가 같은 뉴스를 본다(game-harness §1-A).
 */
export default function MarketNewsFeed({
  events,
  currentTick,
  ticksPerGameDay,
}: {
  events: GameMarketEvent[];
  currentTick: number;
  ticksPerGameDay: number;
}) {
  if (events.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-5">
        <h3 className="text-sm font-bold tracking-tight">시장 뉴스</h3>
        <p className="mt-2 text-xs text-foreground-muted">
          최근 며칠간 특별한 소식이 없습니다.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="text-sm font-bold tracking-tight">시장 뉴스</h3>
      <ul className="mt-3 space-y-2">
        {events.map((e) => {
          const daysAgo = Math.floor((currentTick - e.tick) / ticksPerGameDay);
          const Icon = e.positive ? TrendingUp : TrendingDown;
          return (
            <li key={`${e.tick}-${e.target}`} className="flex items-start gap-2 text-xs">
              <Icon
                size={14}
                strokeWidth={2}
                className={`shrink-0 mt-0.5 ${e.positive ? "text-[#DC2626]" : "text-[#2563EB]"}`}
              />
              <span className="min-w-0 flex-1">
                <span className="block leading-relaxed">{e.headline}</span>
                <span className="block text-[11px] text-foreground-muted">
                  {SCOPE_LABEL[e.scope]}
                  <span className="mx-1 text-border">·</span>
                  {daysAgo === 0 ? "오늘" : `${daysAgo}일 전`}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[11px] text-foreground-muted">
        가상 회사에 대한 게임 내 사건입니다. 실제 기업·시장과 무관합니다.
      </p>
    </div>
  );
}
