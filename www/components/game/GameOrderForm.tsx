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
  // 지정가 예약. 체결가는 지정가 그대로다 — 유리한 갭을 유저 몫으로 주지 않는다(결정론이라 갭 정의가 애매).
  onReserve: (
    side: "LONG" | "SHORT",
    quantity: number,
    leverage: number,
    limitPriceKrw: number,
  ) => void;
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
  onReserve,
}: Props) {
  // 방향·수량을 실시간으로 반영해 예상 금액을 보여준다(REACT_RULES 패턴 B: 단일 객체)
  const [order, setOrder] = useState<{
    side: "LONG" | "SHORT";
    quantity: number;
    leverage: number;
    mode: "market" | "limit";
    limitPriceKrw: number;
  }>({
    side: "LONG",
    quantity: 1,
    leverage: 1,
    mode: "market",
    limitPriceKrw: symbol.priceKrw,
  });

  const feeRate = rules?.feeRate ?? 0;
  const tiers = rules?.leverageTiers ?? [1];
  const isLimit = order.mode === "limit";
  // 지정가는 그 가격에 체결된다(유리한 갭 없음) — 증거금·수수료·청산선 전부 지정가 기준이다.
  const basePrice = isLimit && order.limitPriceKrw > 0 ? order.limitPriceKrw : symbol.priceKrw;
  const notional = basePrice * order.quantity;
  // 증거금 = 명목 ÷ 배율. 수수료는 명목 기준이다(레버리지가 거래비용까지 깎지 않게).
  const principal = Math.floor(notional / order.leverage);
  const fee = Math.round(notional * feeRate);
  const total = principal + fee;
  const maxQuantity = Math.max(
    0,
    Math.floor(investableKrw / (basePrice * (1 / order.leverage + feeRate))),
  );
  const overBudget = total > investableKrw;

  // 청산가 — 백엔드 liquidation_price()와 같은 식. 1배는 청산되지 않는다.
  const margin = rules?.maintenanceMarginRatio ?? 0;
  const liquidationPrice =
    order.leverage <= 1
      ? null
      : Math.round(
          order.side === "LONG"
            ? (basePrice * (1 - 1 / order.leverage)) / (1 - margin)
            : (basePrice * (1 + 1 / order.leverage)) / (1 + margin),
        );
  const expiryGameDays = Math.round((rules?.leveragedExpiryTicks ?? 0) / (rules?.ticksPerGameDay ?? 60));

  const setQuantity = (value: number) =>
    setOrder((prev) => ({ ...prev, quantity: Math.max(1, Math.min(value, 1_000_000)) }));

  // 지정가가 현재가와 같은 방향이면 예약이 의미 없다 — 롱은 현재가보다 낮게(le),
  // 숏은 높게(ge) 잡아야 "닿으면 체결"이 성립한다. 서버도 같은 판정을 하지만
  // 400을 받고서야 알게 하지 않는다.
  const limitOffPct = ((order.limitPriceKrw - symbol.priceKrw) / symbol.priceKrw) * 100;
  const limitWrongSide =
    isLimit &&
    order.limitPriceKrw > 0 &&
    (order.side === "LONG" ? order.limitPriceKrw >= symbol.priceKrw : order.limitPriceKrw <= symbol.priceKrw);

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

      {/* 체결 방식 — 세그먼트 토글이라 Button 스케일과 섞지 않는다(www CLAUDE §4) */}
      <div className="mt-2 grid grid-cols-2 gap-2">
        {(["market", "limit"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => setOrder((prev) => ({ ...prev, mode }))}
            aria-pressed={order.mode === mode}
            className={`h-10 rounded-xl text-sm font-medium border transition-colors ${
              order.mode === mode
                ? "bg-foreground text-background border-transparent"
                : "border-border text-foreground-muted hover:bg-accent"
            }`}
          >
            {mode === "market" ? "시장가" : "지정가"}
          </button>
        ))}
      </div>

      {isLimit && (
        <>
          <label className="mt-4 block text-xs text-foreground-muted" htmlFor="game-limit-price">
            지정가 (현재가 {won(symbol.priceKrw)})
          </label>
          <Input
            id="game-limit-price"
            type="number"
            min={1}
            value={order.limitPriceKrw}
            onChange={(e) =>
              setOrder((prev) => ({ ...prev, limitPriceKrw: Math.max(0, Number(e.target.value)) }))
            }
            className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-brand/30"
          />
          <div className="mt-1.5 grid grid-cols-4 gap-1.5">
            {([-5, -2, 2, 5] as const).map((pct) => (
              <button
                key={pct}
                type="button"
                onClick={() =>
                  setOrder((prev) => ({
                    ...prev,
                    limitPriceKrw: Math.max(1, Math.round(symbol.priceKrw * (1 + pct / 100))),
                  }))
                }
                className="h-8 rounded-lg border border-border text-xs font-medium text-foreground-muted hover:bg-accent tabular-nums"
              >
                {pct > 0 ? `+${pct}%` : `${pct}%`}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-foreground-muted tabular-nums">
            현재가 대비 {limitOffPct >= 0 ? "+" : ""}
            {limitOffPct.toFixed(2)}% ·{" "}
            {order.side === "LONG" ? "이 가격 이하로 내려오면" : "이 가격 이상으로 올라가면"} 체결
          </p>
          {limitWrongSide && (
            <p className="mt-1.5 text-xs text-amber-700 leading-relaxed">
              {order.side === "LONG"
                ? "롱 예약은 현재가보다 낮게 잡아야 합니다 — 지금 가격이면 바로 사면 됩니다."
                : "숏 예약은 현재가보다 높게 잡아야 합니다 — 지금 가격이면 바로 팔면 됩니다."}
            </p>
          )}
        </>
      )}

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
      <Input
        id="game-quantity"
        type="number"
        min={1}
        value={order.quantity}
        onChange={(e) => setQuantity(Number(e.target.value))}
        className="mt-1 w-full h-10 px-3 rounded-xl border border-border bg-background text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-brand/30"
      />
      {/* 투자 가능 금액 대비 비율 버튼 — 레퍼런스(토스증권 주문 패널)의 10/25/50/최대.
          수량을 손으로 세지 않고 "얼마를 쓸지"로 주문하게 한다. */}
      <div className="mt-1.5 grid grid-cols-4 gap-1.5">
        {([10, 25, 50, 100] as const).map((pct) => (
          <button
            key={pct}
            type="button"
            onClick={() => setQuantity(Math.floor((maxQuantity * pct) / 100))}
            disabled={Math.floor((maxQuantity * pct) / 100) < 1}
            className="h-8 rounded-lg border border-border text-xs font-medium text-foreground-muted hover:bg-accent disabled:opacity-40"
          >
            {pct === 100 ? "최대" : `${pct}%`}
          </button>
        ))}
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
          {isLimit && "체결되면 "}
          <b>{won(liquidationPrice)}</b>에 닿으면 강제청산되어 증거금을 잃습니다
          ({isLimit ? "지정가" : "현재가"} 대비{" "}
          {(((liquidationPrice - basePrice) / basePrice) * 100).toFixed(1)}%).
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

      {isLimit && (
        <p className="mt-3 text-xs text-foreground-muted leading-relaxed">
          예약하면 체결에 쓸 <b>{won(total)}</b>이 지금 묶입니다(취소·만료 시 돌아옵니다).
          체결 판정은 이 화면을 열어 둔 동안 이루어집니다.
        </p>
      )}

      <Button
        type="button"
        onClick={() =>
          isLimit
            ? onReserve(order.side, order.quantity, order.leverage, order.limitPriceKrw)
            : onSubmit(order.side, order.quantity, order.leverage)
        }
        disabled={
          disabled ||
          overBudget ||
          order.quantity < 1 ||
          (isLimit && (order.limitPriceKrw < 1 || limitWrongSide))
        }
        size="lg"
              className="mt-4 w-full"
      >
        {overBudget
          ? "투자 가능 금액을 넘습니다"
          : `${order.quantity.toLocaleString()}주 ${isLimit ? "예약" : "주문"}${order.leverage > 1 ? ` · ${order.leverage}배` : ""}`}
      </Button>
    </div>
  );
}
