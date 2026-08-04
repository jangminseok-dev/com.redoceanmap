"use client";

import { TrendingDown, TrendingUp } from "lucide-react";
import type { GameMarketEvent } from "@/lib/types";

const SCOPE_LABEL: Record<GameMarketEvent["scope"], string> = {
  symbol: "종목",
  sector: "업종",
  market: "시장",
};

// 잔여 영향이 이보다 작으면 사실상 가격에서 사라진 뉴스다(테이퍼 종단).
// 백엔드 market_events.event_contribution()이 내려주는 값과 같은 단위(%).
const FADED_IMPACT_PCT = 0.1;

/**
 * 시장 뉴스 — 최근 호재·악재.
 *
 * 저장된 로그가 아니라 **매번 재현되는 값**이다. 같은 틱이면 누가 언제 봐도 같은 목록이라
 * 모든 참가자가 같은 뉴스를 본다(game-harness §1-A).
 *
 * 피드의 대부분은 **다른 종목 뉴스**다(실측: 8건 중 내 종목 관련 0~2건). 구분이 없으면
 * "뉴스가 떴는데 내 주식은 그대로"로 읽히므로, 선택 종목에 걸리는 뉴스를 위로 올리고
 * 배지를 단다. 영향 크기도 함께 보여준다 — 백엔드가 가격에 넣는 값과 같은 숫자다.
 */
export default function MarketNewsFeed({
  events,
  currentTick,
  ticksPerGameDay,
  selectedSymbol,
}: {
  events: GameMarketEvent[];
  currentTick: number;
  ticksPerGameDay: number;
  selectedSymbol?: string;
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

  const isMine = (e: GameMarketEvent) =>
    !!selectedSymbol && e.affectedSymbols.includes(selectedSymbol);

  // 내 종목 뉴스를 위로. 그 안에서는 원래 순서(최신순)를 지킨다.
  const ordered = [...events].sort((a, b) => Number(isMine(b)) - Number(isMine(a)));

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="text-sm font-bold tracking-tight">시장 뉴스</h3>
      <ul className="mt-3 space-y-2">
        {ordered.map((e) => {
          const daysAgo = Math.floor((currentTick - e.tick) / ticksPerGameDay);
          const Icon = e.positive ? TrendingUp : TrendingDown;
          const mine = isMine(e);
          const faded = Math.abs(e.remainingImpactPct) < FADED_IMPACT_PCT;
          return (
            <li
              key={`${e.tick}-${e.target}`}
              className={`flex items-start gap-2 text-xs ${faded ? "opacity-45" : ""}`}
            >
              <Icon
                size={14}
                strokeWidth={2}
                className={`shrink-0 mt-0.5 ${e.positive ? "text-up" : "text-down"}`}
              />
              <span className="min-w-0 flex-1">
                <span className="block leading-relaxed">
                  {mine && (
                    <span className="mr-1.5 rounded-md bg-brand px-1.5 py-0.5 text-xs font-semibold text-white align-middle">
                      내 종목
                    </span>
                  )}
                  {e.headline}
                </span>
                <span className="block text-xs text-foreground-muted">
                  {SCOPE_LABEL[e.scope]}
                  <span className="mx-1 text-border">·</span>
                  {daysAgo === 0 ? "오늘" : `${daysAgo}일 전`}
                  <span className="mx-1 text-border">·</span>
                  {faded ? (
                    "영향 소멸"
                  ) : (
                    <span className="tabular-nums">
                      지금 {e.remainingImpactPct > 0 ? "+" : ""}
                      {e.remainingImpactPct.toFixed(2)}%
                    </span>
                  )}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs leading-relaxed text-foreground-muted">
        뉴스는 가격을 한쪽으로 밀 뿐, 그날의 변동을 이기지 못할 수도 있습니다.
        <br />
        가상 회사에 대한 게임 내 사건입니다. 실제 기업·시장과 무관합니다.
      </p>
    </div>
  );
}
