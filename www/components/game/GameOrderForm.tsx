"use client";

import { useState } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import type { GameRulebook, GameSymbolPrices } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

type Props = {
  symbol: GameSymbolPrices;
  rules: GameRulebook | undefined;
  investableKrw: number;
  disabled: boolean;
  onSubmit: (side: "LONG" | "SHORT", quantity: number, leverage: number) => void;
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
  const [order, setOrder] = useState<{
    side: "LONG" | "SHORT";
    quantity: number;
    leverage: number;
  }>({
    side: "LONG",
    quantity: 1,
    leverage: 1,
  });

  const feeRate = rules?.feeRate ?? 0;
  const tiers = rules?.leverageTiers ?? [1];
  const notional = symbol.priceKrw * order.quantity;
  // 증거금 = 명목 ÷ 배율. 수수료는 명목 기준이다(레버리지가 거래비용까지 깎지 않게).
  const principal = Math.floor(notional / order.leverage);
  const fee = Math.round(notional * feeRate);
  const total = principal + fee;
  const maxQuantity = Math.max(
    0,
    Math.floor(investableKrw / (symbol.priceKrw * (1 / order.leverage + feeRate))),
  );
  const overBudget = total > investableKrw;

  // 청산가 — 백엔드 liquidation_price()와 같은 식. 1배는 청산되지 않는다.
  const margin = rules?.maintenanceMarginRatio ?? 0;
  const liquidationPrice =
    order.leverage <= 1
      ? null
      : Math.round(
          order.side === "LONG"
            ? (symbol.priceKrw * (1 - 1 / order.leverage)) / (1 - margin)
            : (symbol.priceKrw * (1 + 1 / order.leverage)) / (1 + margin),
        );
  const expiryGameDays = Math.round((rules?.leveragedExpiryTicks ?? 0) / (rules?.ticksPerGameDay ?? 60));

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
                    ? "bg-up text-white border-transparent"
                    : "bg-down text-white border-transparent"
                  : "border-border text-foreground-muted hover:bg-accent"
              }`}
            >
              {isLong ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
              {isLong ? "롱 (오를 것)" : "숏 (내릴 것)"}
            </button>
          );
        })}
      </div>

      {tiers.length > 1 && (
        <>
          <p className="mt-4 text-xs text-foreground-muted">레버리지</p>
          <div className="mt-1 grid grid-cols-4 gap-1.5">
            {tiers.map((tier) => (
              <button
                key={tier}
                type="button"
                onClick={() => setOrder((prev) => ({ ...prev, leverage: tier }))}
                aria-pressed={order.leverage === tier}
                className={`h-10 rounded-xl text-sm font-medium border transition-colors ${
                  order.leverage === tier
                    ? "bg-foreground text-background border-transparent"
                    : "border-border text-foreground-muted hover:bg-accent"
                }`}
              >
                {tier}배
              </button>
            ))}
          </div>
        </>
      )}

      <label className="mt-4 block text-xs text-foreground-muted" htmlFor="game-quantity">
        수량
      </label>
      <div className="mt-1 flex gap-2">
        <Input
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
          className="px-3 h-10 rounded-xl border border-border text-xs font-medium text-foreground-muted hover:bg-accent disabled:opacity-40"
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
        {order.leverage > 1 && (
          <div className="flex justify-between">
            <dt className="text-foreground-muted">명목 금액</dt>
            <dd className="tabular-nums">{won(notional)}</dd>
          </div>
        )}
        <div className="flex justify-between">
          <dt className="text-foreground-muted">수수료</dt>
          <dd className="tabular-nums">{won(fee)}</dd>
        </div>
        <div className="flex justify-between font-semibold border-t border-border pt-1 mt-1">
          <dt>합계</dt>
          <dd className={`tabular-nums ${overBudget ? "text-up" : ""}`}>{won(total)}</dd>
        </div>
      </dl>

      {liquidationPrice !== null && (
        <p className="mt-2 rounded-xl bg-amber-50 border border-amber-200 px-3 py-2 text-xs leading-relaxed text-amber-900">
          <b>{won(liquidationPrice)}</b>에 닿으면 강제청산되어 증거금을 잃습니다
          (현재가 대비 {(((liquidationPrice - symbol.priceKrw) / symbol.priceKrw) * 100).toFixed(1)}%).
          <br />
          레버리지 포지션은 게임 {expiryGameDays}일 뒤 자동으로 마감되며, 접속하지 않은 동안에도
          청산될 수 있습니다. 손실은 증거금까지입니다.
        </p>
      )}

      {order.side === "SHORT" && rules && (
        <p className="mt-2 text-xs text-foreground-muted leading-relaxed">
          숏은 증거금 100%이고 손실은 증거금까지입니다. 보유하는 동안 게임 1일마다
          증거금의 {(rules.shortCarryRatePerGameDay * 100).toFixed(2)}%가 비용으로 붙습니다.
        </p>
      )}

      <Button
        type="button"
        onClick={() => onSubmit(order.side, order.quantity, order.leverage)}
        disabled={disabled || overBudget || order.quantity < 1}
        size="lg"
              className="mt-4 w-full"
      >
        {overBudget
          ? "투자 가능 금액을 넘습니다"
          : `${order.quantity.toLocaleString()}주 주문${order.leverage > 1 ? ` · ${order.leverage}배` : ""}`}
      </Button>
    </div>
  );
}
