"use client";

import { useState } from "react";
import type { GameLimitOrder, GamePosition } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

type Props = {
  positions: GamePosition[];
  ticksPerGameDay: number;
  currentTick: number;
  closingId: number | null;
  onClose: (positionId: number) => void;
  // 이 포지션에 걸린 청산 예약(익절·손절). 없으면 빈 배열.
  exitOrders: GameLimitOrder[];
  onSetExit: (positionId: number, takeProfitKrw: number | null, stopLossKrw: number | null) => void;
  exitPendingId: number | null;
};

const won = (v: number) => `${v.toLocaleString()}원`;
const signed = (v: number) => `${v >= 0 ? "+" : ""}${v.toLocaleString()}`;
const toneOf = (v: number) => (v >= 0 ? "text-up" : "text-down");

export default function GamePositionList({
  positions,
  ticksPerGameDay,
  currentTick,
  closingId,
  onClose,
  exitOrders,
  onSetExit,
  exitPendingId,
}: Props) {
  // 어느 포지션의 예약 폼을 펼쳤는가 — 값 하나라 일반 useState(REACT_RULES 우선순위 3).
  // 입력값 자체는 폼 제출이 목적이므로 FormData로 받는다(패턴 A) — controlled state를 만들지 않는다.
  const [editingId, setEditingId] = useState<number | null>(null);

  const submitExit = (positionId: number) => (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = Object.fromEntries(new FormData(e.currentTarget).entries());
    const num = (v: FormDataEntryValue | undefined) => {
      const n = Number(v);
      return v === "" || v === undefined || !Number.isFinite(n) || n <= 0 ? null : Math.round(n);
    };
    onSetExit(positionId, num(form.takeProfit), num(form.stopLoss));
    setEditingId(null);
  };

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
        // 익절·손절 판정은 trigger로 한다 — 롱은 ge가 익절, 숏은 le가 익절이다
        // (백엔드 limit_fill.py와 같은 규칙).
        const mine = exitOrders.filter((o) => o.positionId === p.id);
        const take = mine.find((o) => (isLong ? o.trigger === "ge" : o.trigger === "le"));
        const stop = mine.find((o) => (isLong ? o.trigger === "le" : o.trigger === "ge"));
        return (
          <li key={p.id} className="rounded-2xl border border-border bg-surface p-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <span
                className={`px-2 py-0.5 rounded-md text-xs font-bold text-white ${
                  isLong ? "bg-up" : "bg-down"
                }`}
              >
                {isLong ? "롱" : "숏"}
                {p.leverage > 1 && ` ${p.leverage}배`}
              </span>

              <span className="min-w-0">
                <span className="block text-sm font-semibold truncate">{p.name}</span>
                <span className="block text-xs text-foreground-muted">
                  {p.quantity.toLocaleString()}주 · {won(p.entryPriceKrw)} 진입 · 게임 {heldDays}일 보유
                </span>
              </span>

              <span className="ml-auto text-right">
                <span className="block text-sm tabular-nums">{won(p.currentPriceKrw)}</span>
                <span className={`block text-xs tabular-nums ${toneOf(p.unrealizedPnlKrw)}`}>
                  {signed(p.unrealizedPnlKrw)}원 ({p.unrealizedPct >= 0 ? "+" : ""}
                  {p.unrealizedPct.toFixed(2)}%)
                </span>
                {/* 수수료·숏 캐리를 뺀 실수령액 — 평가손익만 보면 청산 후 잔고와 어긋난다 */}
                <span className="block text-xs text-foreground-muted tabular-nums">
                  지금 청산 시 {won(p.marketValueKrw)}
                </span>
                {p.liquidationPriceKrw !== null && (
                  <span className="block text-xs text-amber-700 tabular-nums">
                    청산선 {won(p.liquidationPriceKrw)}
                    {p.expiresTick !== null &&
                      ` · 게임 ${Math.max(0, Math.ceil((p.expiresTick - currentTick) / ticksPerGameDay))}일 남음`}
                  </span>
                )}
              </span>

              <span className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => setEditingId((prev) => (prev === p.id ? null : p.id))}
                  aria-expanded={editingId === p.id}
                  className="px-3 h-10 rounded-xl border border-border text-xs font-medium hover:bg-accent transition-colors"
                >
                  {take || stop ? "예약 수정" : "익절·손절"}
                </button>
                <button
                  type="button"
                  onClick={() => onClose(p.id)}
                  disabled={closingId !== null}
                  className="px-3 h-10 rounded-xl border border-border text-xs font-medium hover:bg-accent disabled:opacity-40 transition-colors"
                >
                  {closingId === p.id ? "청산 중…" : "청산"}
                </button>
              </span>
            </div>

            {(take || stop) && editingId !== p.id && (
              <p className="mt-2 text-xs text-foreground-muted tabular-nums">
                예약 걸림 — {take ? `익절 ${won(take.limitPriceKrw)}` : "익절 없음"} ·{" "}
                {stop ? `손절 ${won(stop.limitPriceKrw)}` : "손절 없음"}
                {take && stop && " (한쪽이 체결되면 나머지는 취소됩니다)"}
              </p>
            )}

            {editingId === p.id && (
              // 폼 제출이 목적이라 FormData로 받는다(REACT_RULES 패턴 A) — 입력에 value/onChange를 두지 않는다
              <form onSubmit={submitExit(p.id)} className="mt-3 border-t border-border pt-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs text-foreground-muted" htmlFor={`tp-${p.id}`}>
                      익절가 ({isLong ? "이상" : "이하"})
                    </label>
                    <Input
                      id={`tp-${p.id}`}
                      name="takeProfit"
                      type="number"
                      min={0}
                      defaultValue={take?.limitPriceKrw ?? ""}
                      placeholder="비우면 해제"
                      className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-foreground-muted" htmlFor={`sl-${p.id}`}>
                      손절가 ({isLong ? "이하" : "이상"})
                    </label>
                    <Input
                      id={`sl-${p.id}`}
                      name="stopLoss"
                      type="number"
                      min={0}
                      defaultValue={stop?.limitPriceKrw ?? ""}
                      placeholder="비우면 해제"
                      className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums"
                    />
                  </div>
                </div>
                <p className="mt-2 text-xs text-foreground-muted leading-relaxed">
                  현재가 {won(p.currentPriceKrw)} · 진입 {won(p.entryPriceKrw)}. 둘 다 넣으면 한쪽이
                  체결될 때 나머지가 자동 취소됩니다. 강제청산이 예약보다 우선합니다.
                </p>
                <div className="mt-2 flex gap-2">
                  <Button type="submit" size="sm" disabled={exitPendingId !== null}>
                    {exitPendingId === p.id ? "저장 중…" : "예약 저장"}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="weak"
                    onClick={() => setEditingId(null)}
                  >
                    닫기
                  </Button>
                </div>
              </form>
            )}
          </li>
        );
      })}
    </ul>
  );
}
