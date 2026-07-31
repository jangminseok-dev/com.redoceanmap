"use client";

import { useState } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import type { GameRulebook, GameSymbolPrices } from "@/lib/types";

type Props = {
  symbol: GameSymbolPrices;
  rules: GameRulebook | undefined;
  investableKrw: number;
  disabled: boolean;
  onSubmit: (side: "LONG" | "SHORT", quantity: number) => void;
};

const won = (v: number) => `${v.toLocaleString()}원`;

/**
 * 주문 폼.
 *
 * 수수료율·예약금은 서버가 `/game/myself`로 실어 보낸 값을 쓴다 — 프론트가 하드코딩하면
 * 규칙이 바뀔 때 조용히 갈라진다. 최대 수량도 같은 값으로 계산하지만 최종 판정은 서버다.
 */
export default function GameOrderForm({
  symbol,
  rules,
  investableKrw,
  disabled,
  onSubmit,
}: Props) {
  // 방향·수량을 실시간으로 반영해 예상 금액을 보여준다(REACT_RULES 패턴 B: 단일 객체)
  const [order, setOrder] = useState<{ side: "LONG" | "SHORT"; quantity: number }>({
    side: "LONG",
    quantity: 1,
  });

  const feeRate = rules?.feeRate ?? 0;
  const principal = symbol.priceKrw * order.quantity;
  const fee = Math.round(principal * feeRate);
  const total = principal + fee;
  const maxQuantity = Math.max(
    0,
    Math.floor(investableKrw / (symbol.priceKrw * (1 + feeRate))),
  );
  const overBudget = total > investableKrw;

  const setQuantity = (value: number) =>
    setOrder((prev) => ({ ...prev, quantity: Math.max(1, Math.min(value, 1_000_000)) }));

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="text-sm font-bold tracking-tight">
        {symbol.name} <span className="text-foreground-muted font-normal">주문</span>
      </h3>

      <div className="mt-3 grid grid-cols-2 gap-2">
        {(["LONG", "SHORT"] as const).map((side) => {
          const active = order.side === side;
          const isLong = side === "LONG";
          return (
            <button
              key={side}
              type="button"
              onClick={() => setOrder((prev) => ({ ...prev, side }))}
              aria-pressed={active}
              className={`flex items-center justify-center gap-1.5 h-10 rounded-xl text-sm font-medium border transition-colors ${
                active
                  ? isLong
                    ? "bg-[#DC2626] text-white border-transparent"
                    : "bg-[#2563EB] text-white border-transparent"
                  : "border-border text-foreground-muted hover:bg-black/[0.03]"
              }`}
            >
              {isLong ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
              {isLong ? "롱 (오를 것)" : "숏 (내릴 것)"}
            </button>
          );
        })}
      </div>

      <label className="mt-4 block text-xs text-foreground-muted" htmlFor="game-quantity">
        수량
      </label>
      <div className="mt-1 flex gap-2">
        <input
          id="game-quantity"
          type="number"
          min={1}
          value={order.quantity}
          onChange={(e) => setQuantity(Number(e.target.value))}
          className="flex-1 h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-brand/30"
        />
        <button
          type="button"
          onClick={() => setQuantity(maxQuantity)}
          disabled={maxQuantity < 1}
          className="px-3 h-10 rounded-xl border border-border text-xs font-medium text-foreground-muted hover:bg-black/[0.03] disabled:opacity-40"
        >
          최대 {maxQuantity.toLocaleString()}
        </button>
      </div>

      <dl className="mt-4 space-y-1 text-xs">
        <div className="flex justify-between">
          <dt className="text-foreground-muted">
            {order.side === "LONG" ? "매수대금" : "증거금"}
          </dt>
          <dd className="tabular-nums">{won(principal)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-foreground-muted">수수료</dt>
          <dd className="tabular-nums">{won(fee)}</dd>
        </div>
        <div className="flex justify-between font-semibold border-t border-border pt-1 mt-1">
          <dt>합계</dt>
          <dd className={`tabular-nums ${overBudget ? "text-[#DC2626]" : ""}`}>{won(total)}</dd>
        </div>
      </dl>

      {order.side === "SHORT" && rules && (
        <p className="mt-2 text-[11px] text-foreground-muted leading-relaxed">
          숏은 증거금 100%이고 손실은 증거금까지입니다. 보유하는 동안 게임 1일마다
          증거금의 {(rules.shortCarryRatePerGameDay * 100).toFixed(2)}%가 비용으로 붙습니다.
        </p>
      )}

      <button
        type="button"
        onClick={() => onSubmit(order.side, order.quantity)}
        disabled={disabled || overBudget || order.quantity < 1}
        className="mt-4 w-full h-11 rounded-xl bg-brand text-white text-sm font-semibold hover:bg-brand-deep disabled:opacity-40 disabled:hover:bg-brand transition-colors"
      >
        {overBudget ? "투자 가능 금액을 넘습니다" : `${order.quantity.toLocaleString()}주 주문`}
      </button>
    </div>
  );
}
