"use client";

import type { GamePosition } from "@/lib/types";

type Props = {
  positions: GamePosition[];
  ticksPerGameDay: number;
  currentTick: number;
  closingId: number | null;
  onClose: (positionId: number) => void;
};

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toLocaleString()}`;
const toneOf = (v: number) => (v >= 0 ? "text-[#DC2626]" : "text-[#2563EB]");

export default function GamePositionList({
  positions,
  ticksPerGameDay,
  currentTick,
  closingId,
  onClose,
}: Props) {
  if (positions.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-surface p-8 text-center">
        <p className="text-sm text-foreground-muted">보유 중인 포지션이 없습니다.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {positions.map((p) => {
        const isLong = p.side === "LONG";
        const heldDays = Math.max(0, Math.floor((currentTick - p.entryTick) / ticksPerGameDay));
        return (
          <li
            key={p.id}
            className="rounded-2xl border border-border bg-surface p-4 flex flex-wrap items-center gap-x-4 gap-y-2"
          >
            <span
              className={`px-2 py-0.5 rounded-md text-[11px] font-bold text-white ${
                isLong ? "bg-[#DC2626]" : "bg-[#2563EB]"
              }`}
            >
              {isLong ? "롱" : "숏"}
              {p.leverage > 1 && ` ${p.leverage}배`}
            </span>

            <span className="min-w-0">
              <span className="block text-sm font-semibold truncate">{p.name}</span>
              <span className="block text-[11px] text-foreground-muted">
                {p.quantity.toLocaleString()}주 · {won(p.entryPriceKrw)} 진입 · 게임 {heldDays}일 보유
              </span>
            </span>

            <span className="ml-auto text-right">
              <span className="block text-sm tabular-nums">{won(p.currentPriceKrw)}</span>
              <span className={`block text-[11px] tabular-nums ${toneOf(p.unrealizedPnlKrw)}`}>
                {signed(p.unrealizedPnlKrw)}원 ({p.unrealizedPct >= 0 ? "+" : ""}
                {p.unrealizedPct.toFixed(2)}%)
              </span>
              {/* 수수료·숏 캐리를 뺀 실수령액 — 평가손익만 보면 청산 후 잔고와 어긋난다 */}
              <span className="block text-[11px] text-foreground-muted tabular-nums">
                지금 청산 시 {won(p.marketValueKrw)}
              </span>
              {p.liquidationPriceKrw !== null && (
                <span className="block text-[11px] text-amber-700 tabular-nums">
                  청산선 {won(p.liquidationPriceKrw)}
                  {p.expiresTick !== null &&
                    ` · 게임 ${Math.max(0, Math.ceil((p.expiresTick - currentTick) / ticksPerGameDay))}일 남음`}
                </span>
              )}
            </span>

            <button
              type="button"
              onClick={() => onClose(p.id)}
              disabled={closingId !== null}
              className="px-3 h-10 rounded-xl border border-border text-xs font-medium hover:bg-accent disabled:opacity-40 transition-colors"
            >
              {closingId === p.id ? "청산 중…" : "청산"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
