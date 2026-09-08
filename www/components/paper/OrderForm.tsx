"use client";

import { useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, placePaperOrder } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fmtPrice } from "./format";

const ACTIONS = [
  { value: "BUY", label: "매수" },
  { value: "SELL", label: "매도" },
  { value: "SHORT", label: "숏 진입" },
  { value: "COVER", label: "숏 청산" },
] as const;

/** 사람 주문 — 폼 제출 흐름이라 FormData 패턴(REACT_RULES 패턴 A). 체결은 즉시, 최신 저장 봉 종가. */
export default function OrderForm({ suggestions = [] }: { suggestions?: string[] }) {
  const queryClient = useQueryClient();
  const tickerRef = useRef<HTMLInputElement>(null);
  const order = useMutation({
    mutationFn: placePaperOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-me"] });
      queryClient.invalidateQueries({ queryKey: ["paper-board"] });
    },
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const ticker = String(formData.get("ticker") ?? "").trim().toUpperCase();
    const action = String(formData.get("action")) as (typeof ACTIONS)[number]["value"];
    const quantity = Number(formData.get("quantity"));
    if (!ticker || !(quantity >= 1)) return;
    order.mutate({ ticker, action, quantity });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <fieldset>
        <legend className="text-xs font-medium">주문</legend>
        <div className="mt-1.5 flex flex-wrap gap-2">
          {ACTIONS.map((a) => (
            <label key={a.value} className="cursor-pointer">
              <input type="radio" name="action" value={a.value} defaultChecked={a.value === "BUY"} required className="peer sr-only" />
              <span className="inline-flex items-center rounded-full border border-border px-3 py-1.5 text-sm text-foreground-muted peer-checked:border-brand peer-checked:bg-brand/10 peer-checked:font-medium peer-checked:text-brand">
                {a.label}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <span className="text-xs text-foreground-muted self-center">AI가 들고 있는 종목:</span>
          {suggestions.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => {
                if (tickerRef.current) tickerRef.current.value = t;
              }}
              className="inline-flex items-center h-7 px-2.5 rounded-full border border-border text-xs text-foreground-muted hover:bg-accent hover:text-foreground transition-colors"
            >
              {t}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="paper-ticker" className="text-xs font-medium">종목</Label>
          <Input ref={tickerRef} id="paper-ticker" name="ticker" placeholder="AAPL · 005930.KS" className="w-36" autoComplete="off" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="paper-qty" className="text-xs font-medium">수량</Label>
          <Input id="paper-qty" name="quantity" type="number" min={1} step={1} placeholder="10" className="w-28" />
        </div>
        <Button type="submit" size="lg" loading={order.isPending}>주문</Button>
      </div>
      {order.isError && (
        <p className="text-xs text-brand">{order.error instanceof ApiError ? order.error.message : "주문에 실패했습니다."}</p>
      )}
      {order.isSuccess && (
        <p className="text-xs text-foreground-muted tabular-nums">
          체결 {order.data.ticker} {order.data.quantity}주 @ {fmtPrice(order.data.price, order.data.ticker)} · 수수료{" "}
          {Math.round(order.data.fee_krw).toLocaleString("ko-KR")}원 · 시세 기준{" "}
          {new Date(order.data.price_as_of).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}
        </p>
      )}
      <p className="text-xs text-foreground-muted">워치리스트 종목만 거래되며 체결가는 최신 저장 봉 종가(지연)입니다. 매도·숏 청산은 보유 수량 이내.</p>
    </form>
  );
}
